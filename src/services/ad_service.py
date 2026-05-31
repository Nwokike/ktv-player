import asyncio
import logging
from collections.abc import Callable

import flet as ft

from core.constants import AD_PRELOAD_MAX_RETRIES, AD_PRELOAD_RETRY_DELAY

try:
    import flet_ads as fta

    _HAS_FLET_ADS = True
except ImportError:
    _HAS_FLET_ADS = False

logger = logging.getLogger(__name__)


class AdService:
    BANNER_ID = "ca-app-pub-5679949845754640/5591770463"
    INTERSTITIAL_ID = "ca-app-pub-5679949845754640/8701238822"

    def __init__(self, page: ft.Page):
        self.page = page
        self.interstitial: fta.InterstitialAd | None = None
        self._on_interstitial_close: Callable | None = None
        self._preload_retry_count: int = 0
        self._ad_closed_event: asyncio.Event | None = None

    def get_banner_unit_id(self) -> str:
        return self.BANNER_ID

    def get_interstitial_unit_id(self) -> str:
        return self.INTERSTITIAL_ID

    def _create_ad_container(self, ad_control: ft.Control, width: int) -> ft.Control:
        return ft.Container(
            content=ft.Column(
                [
                    ad_control,
                    ft.Text(
                        "This app is 100% free. Ads help support the developer.",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
            ),
            width=width,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding(0, 10, 0, 10),
        )

    def get_native_style_ad(self) -> ft.Control | None:
        if not _HAS_FLET_ADS or not self.page.platform.is_mobile():
            return None
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=300,
                height=250,
                on_error=lambda e: None,
            )
            return self._create_ad_container(ad, width=300)
        except Exception:
            return None

    def get_standard_banner_ad(self) -> ft.Control | None:
        if not _HAS_FLET_ADS or not self.page.platform.is_mobile():
            return None
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=320,
                height=100,
                on_error=lambda e: None,
            )
            return self._create_ad_container(ad, width=320)
        except Exception:
            return None

    def get_anchor_banner_ad(self) -> ft.Control | None:
        if not _HAS_FLET_ADS or not self.page.platform.is_mobile():
            return None
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=320,
                height=50,
                on_error=lambda e: None,
            )
            return ft.Container(
                content=ad,
                width=320,
                height=50,
                alignment=ft.Alignment.CENTER,
            )
        except Exception:
            return None

    async def preload_interstitial(self, on_close: Callable | None = None):
        self._on_interstitial_close = on_close
        try:
            if not _HAS_FLET_ADS or not self.page.platform.is_mobile():
                return

            logger.info("Preloading new InterstitialAd...")
            self.interstitial = fta.InterstitialAd(
                unit_id=self.get_interstitial_unit_id(),
                on_load=lambda e: logger.info("Interstitial ad preloaded successfully"),
                on_error=lambda e: self._on_preload_error(e, on_close),
                on_close=self._handle_close,
            )
            self._preload_retry_count = 0
        except Exception:
            logger.exception("Failed to preload InterstitialAd")
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
        if self.interstitial is None:
            await self.preload_interstitial(on_close)

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

        # If we have a preloaded ad, show it
        if self.interstitial:
            try:
                logger.info("Showing preloaded interstitial ad...")
                self._ad_closed_event = asyncio.Event()
                await self.interstitial.show()
                # Wait for user to close it (with 30s timeout safety)
                try:
                    await asyncio.wait_for(self._ad_closed_event.wait(), timeout=30.0)
                except asyncio.TimeoutError:
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
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for on-demand interstitial ad")
            return ad_shown
        except Exception:
            logger.exception("Failed to create on-demand interstitial ad")
            return False
