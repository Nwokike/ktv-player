import flet as ft
from core.theme import AppTheme
from core.state import state
from services.iptv_service import iptv_service
from services.ad_service import AdManager
from services.lifecycle import LifecycleManager
from database.manager import db_manager
from views.splash import SplashView
from views.dashboard import DashboardView
from views.player_view import PlayerView
import base64

async def main(page: ft.Page):
    page.title = "KTV Player"
    page.theme = AppTheme.get_theme()
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.spacing = 0
    
    # Initialize Services
    ad_manager = AdManager(page)
    lifecycle_manager = LifecycleManager(page)
    await db_manager.init_db()
    
    # Preload Ad
    await ad_manager.preload_interstitial()

    async def navigate(route: str):
        page.route = route
        page.update()

    async def play_stream(url: str):
        # 1. Save to history
        await db_manager.save_history(url)
        state.add_to_history(url)
        
        # 2. Show Interstitial Ad (Waterfall Fallback)
        ad_shown = await ad_manager.show_interstitial()
        if not ad_shown:
            print("Ad failed to show, proceeding to video...")
            
        # 3. Navigate to player
        encoded_url = base64.b64encode(url.encode()).decode()
        await navigate(f"/play/{encoded_url}")

    async def load_channels():
        state.is_loading = True
        page.update()
        
        # Try local cache first
        cached = iptv_service.load_cached_channels()
        if cached:
            state.channels = cached
            state.is_loading = False
            page.update()
        
        # Fetch fresh list from IPTV-org (Waterfall: Category fallback)
        urls = [
            "https://iptv-org.github.io/iptv/index.m3u",
            "https://iptv-org.github.io/iptv/index.category.m3u"
        ]
        
        for url in urls:
            fresh_channels = await iptv_service.fetch_playlist(url)
            if fresh_channels:
                state.channels = fresh_channels
                await iptv_service.cache_channels(fresh_channels)
                break
        
        state.is_loading = False
        page.update()

    def route_change(e: ft.RouteChangeEvent):
        page.views.clear()
        
        # Splash View (Root)
        if page.route == "/":
            page.views.append(
                ft.View(
                    "/",
                    [SplashView(on_complete=lambda: navigate("/dashboard"))],
                    padding=0
                )
            )
        
        # Dashboard View
        elif page.route == "/dashboard":
            page.views.append(
                ft.View(
                    "/dashboard",
                    [DashboardView(on_play=play_stream)],
                    padding=0
                )
            )
            # Trigger channel load if empty
            if not state.channels:
                ft.page_task(load_channels())

        # Player View
        elif page.route.startswith("/play/"):
            try:
                encoded_url = page.route.replace("/play/", "")
                url = base64.b64decode(encoded_url).decode()
                page.views.append(
                    ft.View(
                        page.route,
                        [PlayerView(url=url, on_back=lambda: navigate("/dashboard"))],
                        padding=0
                    )
                )
            except Exception as e:
                print(f"Deep link error: {e}")
                page.go("/dashboard")

        page.update()

    def view_pop(e: ft.ViewPopEvent):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    # Initial Navigation
    await navigate("/")

if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
