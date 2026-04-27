import flet as ft
import flet_ads as fta
from typing import Optional, Callable

class AdManager:
    # Test Unit IDs
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

    async def preload_interstitial(self, on_close: Optional[Callable] = None):
        """
        Creates and appends a new InterstitialAd to the page overlay.
        """
        self._on_interstitial_close = on_close
        
        # Clean up existing one if any
        if self.interstitial and self.interstitial in self.page.overlay:
            self.page.overlay.remove(self.interstitial)

        try:
            self.interstitial = fta.InterstitialAd(
                unit_id=self.get_interstitial_unit_id(),
                on_load=lambda e: print("Interstitial loaded"),
                on_error=lambda e: print(f"Interstitial error: {e.data}"),
                on_close=self._handle_close
            )
            self.page.overlay.append(self.interstitial)
        except ft.FletUnsupportedPlatformException:
            print(f"Ads not supported on {self.page.platform}. Ad logic will be bypassed.")
            self.interstitial = None
        except Exception as e:
            print(f"Unexpected ad error: {e}")
            self.interstitial = None
            
        self.page.update()

    async def _handle_close(self, e):
        print("Interstitial closed")
        if self.interstitial in self.page.overlay:
            self.page.overlay.remove(self.interstitial)
        
        if self._on_interstitial_close:
            await self._on_interstitial_close()
        
        # Preload the next one immediately
        await self.preload_interstitial(on_close=self._on_interstitial_close)

    async def show_interstitial(self) -> bool:
        """
        Shows the preloaded interstitial. Returns True if shown, False otherwise.
        """
        if self.interstitial:
            try:
                await self.interstitial.show()
                return True
            except Exception as e:
                print(f"Failed to show interstitial: {e}")
                return False
        return False

    def create_banner(self) -> fta.BannerAd:
        """
        Creates a new BannerAd instance.
        """
        return fta.BannerAd(
            unit_id=self.get_banner_unit_id(),
            on_load=lambda e: print("Banner loaded"),
            on_error=lambda e: print(f"Banner error: {e.data}")
        )
