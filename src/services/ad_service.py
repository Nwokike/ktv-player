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
        self._preload_retry_count = 0

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

            self.interstitial = fta.InterstitialAd(
                unit_id=self.get_interstitial_unit_id(),
                on_load=lambda e: None,
                on_error=lambda e: self._handle_preload_error(on_close),
                on_close=self._handle_close,
            )
            self._preload_retry_count = 0
        except Exception:
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
        if self._on_interstitial_close:
            if asyncio.iscoroutinefunction(self._on_interstitial_close):
                self.page.run_task(self._on_interstitial_close)
            else:
                self._on_interstitial_close()

        self.page.run_task(self.preload_interstitial, on_close=self._on_interstitial_close)

    async def show_interstitial(self) -> bool:
        if self.interstitial:
            try:
                await self.interstitial.show()
                return True
            except Exception:
                return False
        return False
