import asyncio
import logging
from collections.abc import Callable

import flet as ft

from core.constants import AD_PRELOAD_MAX_RETRIES, AD_PRELOAD_RETRY_DELAY

try:
    import flet_ads as fta
    from flet_ads.native_ad import NativeAd
    from flet_ads.types import (
        NativeAdTemplateStyle,
        NativeAdTemplateTextStyle,
        NativeAdTemplateType,
        NativeTemplateFontStyle,
    )

    _HAS_FLET_ADS = True
except ImportError:
    _HAS_FLET_ADS = False

logger = logging.getLogger(__name__)


class AdService:
    BANNER_ID = "ca-app-pub-5679949845754640/5591770463"
    INTERSTITIAL_ID = "ca-app-pub-5679949845754640/8701238822"
    NATIVE_ID = "ca-app-pub-5679949845754640/3451279517"

    def __init__(self, page: ft.Page):
        self.page = page
        self.interstitial: fta.InterstitialAd | None = None
        self._on_interstitial_close: Callable | None = None
        self._preload_retry_count: int = 0
        self._ad_closed_event: asyncio.Event | None = None
        self._ad_loaded_event: asyncio.Event | None = None
        self._can_request_ads: bool = True
        self._consent_manager = None
        self._is_shutting_down: bool = False

    def get_banner_unit_id(self) -> str:
        return self.BANNER_ID

    def get_interstitial_unit_id(self) -> str:
        return self.INTERSTITIAL_ID

    def get_native_unit_id(self) -> str:
        return self.NATIVE_ID

    # ── Consent Management (UMP) ──────────────────────────────────────────────

    async def gather_consent(self):
        """Run UMP consent flow. Only shows UI in regulated regions (EEA/UK)."""
        if not _HAS_FLET_ADS:
            self._can_request_ads = True
            return
        try:
            if not self.page.platform.is_mobile():
                self._can_request_ads = True
                return
        except Exception:
            self._can_request_ads = True
            return
        try:
            self._consent_manager = fta.ConsentManager()
            await self._consent_manager.request_consent_info_update()
            await self._consent_manager.load_and_show_consent_form_if_required()
            self._can_request_ads = await self._consent_manager.can_request_ads()
        except Exception as e:
            logger.warning("UMP consent flow failed, defaulting to allow ads: %s", e)
            self._can_request_ads = True

    async def show_privacy_options(self):
        """Show privacy options form if required by regulation (GDPR)."""
        if not self._consent_manager:
            return
        try:
            status = (
                await self._consent_manager.get_privacy_options_requirement_status()
            )
            if status == fta.PrivacyOptionsRequirementStatus.REQUIRED:
                await self._consent_manager.show_privacy_options_form()
                self._can_request_ads = await self._consent_manager.can_request_ads()
        except Exception:
            pass

    # ── Ad Controls ───────────────────────────────────────────────────────────

    def _create_ad_container(self, ad_control: ft.Control) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ad_control,
                    ft.Text(
                        "This app is 100% free. Ads help support the developer.",
                        size=10,
                        color=ft.Colors.with_opacity(0.5, ft.Colors.ON_SURFACE),
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            alignment=ft.Alignment.CENTER,
            padding=6,
            border_radius=16,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            margin=ft.Margin(14, 4, 14, 4),
            expand=True,
        )

    def _get_native_template_style(
        self, template_type: NativeAdTemplateType
    ) -> NativeAdTemplateStyle:
        return NativeAdTemplateStyle(
            template_type=template_type,
            main_bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
            corner_radius=12,
            call_to_action_text_style=NativeAdTemplateTextStyle(
                text_color=ft.Colors.WHITE,
                bgcolor=ft.Colors.PRIMARY,
                style=NativeTemplateFontStyle.BOLD,
            ),
            primary_text_style=NativeAdTemplateTextStyle(
                text_color=ft.Colors.ON_SURFACE,
                style=NativeTemplateFontStyle.BOLD,
                size=13,
            ),
            secondary_text_style=NativeAdTemplateTextStyle(
                text_color=ft.Colors.with_opacity(0.7, ft.Colors.ON_SURFACE),
                size=11,
            ),
            tertiary_text_style=NativeAdTemplateTextStyle(
                text_color=ft.Colors.PRIMARY,
                size=10,
            ),
        )

    def get_native_ad(
        self, template_type: NativeAdTemplateType = NativeAdTemplateType.SMALL
    ) -> ft.Control | None:
        if (
            not _HAS_FLET_ADS
            or not self.page.platform.is_mobile()
            or not self._can_request_ads
        ):
            return None
        try:
            h_val = 250 if template_type == NativeAdTemplateType.MEDIUM else 90
            ad = NativeAd(
                unit_id=self.get_native_unit_id(),
                template_style=self._get_native_template_style(template_type),
                width=320,
                height=h_val,
                on_error=lambda e: logger.debug("Native ad error: %s", e),
            )
            return self._create_ad_container(ad)
        except Exception as ex:
            logger.debug("Failed to instantiate NativeAd: %s", ex)
            return None

    def get_native_style_ad(self) -> ft.Control | None:
        return self.get_native_ad(NativeAdTemplateType.MEDIUM)

    def get_standard_banner_ad(self) -> ft.Control | None:
        if (
            not _HAS_FLET_ADS
            or not self.page.platform.is_mobile()
            or not self._can_request_ads
        ):
            return None
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=320,
                height=100,
                on_error=lambda e: None,
            )
            return self._create_ad_container(ad)
        except Exception:
            return None

    def get_anchor_banner_ad(self) -> ft.Control | None:
        if (
            not _HAS_FLET_ADS
            or not self.page.platform.is_mobile()
            or not self._can_request_ads
        ):
            return None
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=320,
                height=50,
                on_error=lambda e: None,
            )
            return self._create_ad_container(ad)
        except Exception:
            return None

    async def preload_interstitial(self, on_close: Callable | None = None):
        self._on_interstitial_close = on_close
        self._ad_loaded_event = asyncio.Event()
        try:
            if (
                not _HAS_FLET_ADS
                or not self.page.platform.is_mobile()
                or not self._can_request_ads
            ):
                self._ad_loaded_event.set()
                return

            logger.info("Preloading new InterstitialAd...")
            self.interstitial = fta.InterstitialAd(
                unit_id=self.get_interstitial_unit_id(),
                on_load=lambda e: (
                    logger.info("Interstitial ad preloaded successfully"),
                    self._ad_loaded_event.set(),
                ),
                on_error=lambda e: (
                    self._on_preload_error(e, on_close),
                    self._ad_loaded_event.set(),
                ),
                on_close=self._handle_close,
            )
            self._preload_retry_count = 0
        except Exception:
            logger.exception("Failed to preload InterstitialAd")
            if self._ad_loaded_event:
                self._ad_loaded_event.set()
            self._handle_preload_error(on_close)

    def _on_preload_error(self, e, on_close: Callable | None = None):
        logger.error(
            "Interstitial preload error: %s", e.data if hasattr(e, "data") else e
        )
        self._handle_preload_error(on_close)

    def _handle_preload_error(self, on_close: Callable | None = None):
        self.interstitial = None
        if self._preload_retry_count < AD_PRELOAD_MAX_RETRIES:
            self.page.run_task(self._retry_preload, on_close)

    async def _retry_preload(self, on_close: Callable | None = None):
        self._preload_retry_count += 1
        await asyncio.sleep(AD_PRELOAD_RETRY_DELAY)
        if self.interstitial is None and not self._is_shutting_down:
            await self.preload_interstitial(on_close)

    async def close(self):
        """Cancel pending retries and release resources."""
        self._is_shutting_down = True
        self.interstitial = None

    async def _handle_close(self, e):
        logger.info("Interstitial ad closed by user")
        self.interstitial = None

        if self._ad_closed_event is not None:
            self._ad_closed_event.set()

        if self._on_interstitial_close:
            if asyncio.iscoroutinefunction(self._on_interstitial_close):
                self.page.run_task(self._on_interstitial_close)
            else:
                self._on_interstitial_close()

        # Preload the next interstitial ad immediately for the next playback
        self.page.run_task(
            self.preload_interstitial,
            on_close=self._on_interstitial_close,
        )

    async def show_interstitial(self) -> bool:
        if not _HAS_FLET_ADS or not self.page.platform.is_mobile():
            return False

        # If we have a preloaded ad, wait for it to actually finish loading
        if self.interstitial:
            if self._ad_loaded_event and not self._ad_loaded_event.is_set():
                logger.info("Waiting for interstitial ad to finish loading...")
                try:
                    await asyncio.wait_for(self._ad_loaded_event.wait(), timeout=10.0)
                except TimeoutError:
                    logger.warning(
                        "Preloaded ad not ready within 10s, falling back to on-demand",
                    )
                    self.interstitial = None

            # Ad finished loading successfully — show it
            if self.interstitial:
                try:
                    logger.info("Showing preloaded interstitial ad...")
                    self._ad_closed_event = asyncio.Event()
                    await self.interstitial.show()
                    try:
                        await asyncio.wait_for(
                            self._ad_closed_event.wait(), timeout=30.0
                        )
                    except TimeoutError:
                        logger.warning(
                            "Timed out waiting for preloaded interstitial ad to close",
                        )
                    return True
                except Exception:
                    logger.exception("Failed to show preloaded interstitial ad")
                    if self._ad_closed_event is not None:
                        self._ad_closed_event.set()
                    self.interstitial = None

        # If no ad is preloaded (or it failed), load and show a fresh ad on-demand
        logger.info("No preloaded ad ready. Loading fresh ad on-demand...")
        ad_closed = asyncio.Event()
        ad_shown = False

        async def show_on_load(e):
            nonlocal ad_shown
            try:
                logger.info("On-demand interstitial ad loaded. Showing now...")
                ad_shown = True
                await fresh_ad.show()
            except Exception:
                logger.exception("Failed to show on-demand ad")
                ad_closed.set()

        def handle_error(e):
            err = e.data if hasattr(e, "data") else str(e)
            logger.error("On-demand ad error: %s", err)
            ad_closed.set()

        def handle_close(e):
            logger.info("On-demand ad closed by user")
            ad_closed.set()
            # Start preloading a new background ad for the next playback session
            self.page.run_task(self.preload_interstitial)

        try:
            fresh_ad = fta.InterstitialAd(
                unit_id=self.get_interstitial_unit_id(),
                on_load=show_on_load,
                on_error=handle_error,
                on_close=handle_close,
            )
            # Wait up to 10 seconds for the ad to load and show. If it fails or takes
            # too long, timeout and let the video play so the user isn't stuck.
            try:
                await asyncio.wait_for(ad_closed.wait(), timeout=10.0)
            except TimeoutError:
                logger.warning("Timed out waiting for on-demand interstitial ad")
            return ad_shown
        except Exception:
            logger.exception("Failed to create on-demand interstitial ad")
            return False
