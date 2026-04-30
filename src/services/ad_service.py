import flet as ft
import flet_ads as fta
import asyncio
from typing import Optional, Callable


class AdService:
    BANNER_ID = "ca-app-pub-5679949845754640/5591770463"
    INTERSTITIAL_ID = "ca-app-pub-5679949845754640/8701238822"

    def __init__(self, page: ft.Page):
        self.page = page
        self.interstitial: Optional[fta.InterstitialAd] = None
        self._on_interstitial_close: Optional[Callable] = None

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

    def get_native_style_ad(self) -> ft.Control:
        if not self.page.platform.is_mobile():
            return ft.Container(width=0, height=0)
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=300,
                height=250,
                on_error=lambda e: None,
            )
            return self._create_ad_container(ad, width=300)
        except Exception:
            return ft.Container(width=0, height=0)

    def get_standard_banner_ad(self) -> ft.Control:
        if not self.page.platform.is_mobile():
            return ft.Container(width=0, height=0)
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=320,
                height=100,
                on_error=lambda e: None,
            )
            return self._create_ad_container(ad, width=320)
        except Exception:
            return ft.Container(width=0, height=0)

    def get_anchor_banner_ad(self) -> ft.Control:
        if not self.page.platform.is_mobile():
            return ft.Container(width=0, height=0)
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=320,
                height=50,
                on_error=lambda e: None,
            )
            # Anchor banners don't need padding/text, just the ad itself centered
            return ft.Container(
                content=ad,
                width=320,
                height=50,
                alignment=ft.Alignment.CENTER,
            )
        except Exception:
            return ft.Container(width=0, height=0)

    async def preload_interstitial(self, on_close: Optional[Callable] = None):
        self._on_interstitial_close = on_close
        try:
            if not self.page.platform.is_mobile():
                return

            self.interstitial = fta.InterstitialAd(
                unit_id=self.get_interstitial_unit_id(),
                on_load=lambda e: None,
                on_error=lambda e: None,
                on_close=self._handle_close,
            )
        except Exception:
            self.interstitial = None

    async def _handle_close(self, e):
        if self._on_interstitial_close:
            if asyncio.iscoroutinefunction(self._on_interstitial_close):
                await self._on_interstitial_close()
            else:
                self._on_interstitial_close()

        await self.preload_interstitial(on_close=self._on_interstitial_close)

    async def show_interstitial(self) -> bool:
        if self.interstitial:
            try:
                await self.interstitial.show()
                return True
            except Exception:
                return False
        return False
