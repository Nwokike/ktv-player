import flet as ft
import flet_ads as fta
import asyncio
from typing import Optional, Callable

class AdService:
    # Official Google Test Unit IDs
    ANDROID_BANNER = "ca-app-pub-3940256099942544/6300978111"
    ANDROID_INTERSTITIAL = "ca-app-pub-3940256099942544/1033173712"
    
    IOS_BANNER = "ca-app-pub-3940256099942544/2934735716"
    IOS_INTERSTITIAL = "ca-app-pub-3940256099942544/4411468910"

    def __init__(self, page: ft.Page):
        self.page = page
        self.interstitial: Optional[fta.InterstitialAd] = None
        self._on_interstitial_close: Optional[Callable] = None

    def get_banner_unit_id(self) -> str:
        if self.page.platform == ft.PagePlatform.IOS:
            return self.IOS_BANNER
        return self.ANDROID_BANNER

    def get_interstitial_unit_id(self) -> str:
        if self.page.platform == ft.PagePlatform.IOS:
            return self.IOS_INTERSTITIAL
        return self.ANDROID_INTERSTITIAL

    def _create_ad_container(self, ad_control: ft.Control, width: int) -> ft.Control:
        """Wraps the ad with the polite 'Support the developer' text."""
        return ft.Container(
            content=ft.Column(
                [
                    ad_control,
                    ft.Text(
                        "This app is 100% free. Ads help support the developer.",
                        size=11,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                        text_align=ft.TextAlign.CENTER,
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=5,
            ),
            width=width,
            alignment=ft.alignment.center,
            padding=ft.Padding(0, 10, 0, 10)
        )

    def get_native_style_ad(self) -> ft.Control:
        """Returns a 300x250 Medium Rectangle ad with support text."""
        if not self.page.platform.is_mobile():
            return ft.Container(width=0, height=0)
        
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=300,
                height=250,
                on_error=lambda e: print(f"Native Ad error: {e.data}")
            )
            return self._create_ad_container(ad, width=300)
        except Exception as e:
            print(f"Ad rendering skipped: {e}")
            return ft.Container(width=0, height=0)

    def get_standard_banner_ad(self) -> ft.Control:
        """Returns a 320x100 Large Banner ad with support text."""
        if not self.page.platform.is_mobile():
            return ft.Container(width=0, height=0)
        
        try:
            ad = fta.BannerAd(
                unit_id=self.get_banner_unit_id(),
                width=320,
                height=100,
                on_error=lambda e: print(f"Banner Ad error: {e.data}")
            )
            return self._create_ad_container(ad, width=320)
        except Exception as e:
            print(f"Ad rendering skipped: {e}")
            return ft.Container(width=0, height=0)

    async def preload_interstitial(self, on_close: Optional[Callable] = None):
        """Creates and appends a new InterstitialAd to the page overlay."""
        self._on_interstitial_close = on_close
        
        if self.interstitial and self.interstitial in self.page.overlay:
            self.page.overlay.remove(self.interstitial)

        try:
            if not self.page.platform.is_mobile():
                return
                
            self.interstitial = fta.InterstitialAd(
                unit_id=self.get_interstitial_unit_id(),
                on_load=lambda e: print("Interstitial loaded"),
                on_error=lambda e: print(f"Interstitial error: {e.data}"),
                on_close=self._handle_close
            )
            self.page.overlay.append(self.interstitial)
            self.page.update()
        except Exception as e:
            print(f"Unexpected ad error: {e}")
            self.interstitial = None

    async def _handle_close(self, e):
        print("Interstitial closed")
        if self.interstitial in self.page.overlay:
            self.page.overlay.remove(self.interstitial)
        
        if self._on_interstitial_close:
            if asyncio.iscoroutinefunction(self._on_interstitial_close):
                await self._on_interstitial_close()
            else:
                self._on_interstitial_close()
        
        # Preload the next one immediately so it's ready for the next click
        await self.preload_interstitial(on_close=self._on_interstitial_close)

    async def show_interstitial(self) -> bool:
        """Shows the preloaded interstitial. Returns True if shown, False otherwise."""
        if self.interstitial:
            try:
                await self.interstitial.show()
                return True
            except Exception as e:
                print(f"Failed to show interstitial: {e}")
                return False
        return False