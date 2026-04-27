import flet as ft
from core.theme import AppTheme
from core.state import state
from services.iptv_service import iptv_service
# from services.ad_service import AdManager
from services.lifecycle import LifecycleManager
from database.manager import db_manager
from views.splash import SplashView
from views.dashboard import DashboardView
from views.player_view import PlayerView
from views.onboarding import OnboardingView
import base64
import urllib.parse
import warnings

async def main(page: ft.Page):
    page.title = "KTV Player"
    page.favicon = "icon.png"
    page.theme = AppTheme.get_light_theme()
    page.dark_theme = AppTheme.get_dark_theme()
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.padding = 0
    page.spacing = 0
    
    # Initialize Services
    lifecycle_manager = LifecycleManager(page)
    await db_manager.init_db()
    
    # Load settings from DB
    state.user_country = await db_manager.get_setting("user_country", "")
    state.has_accepted_terms = await db_manager.get_setting("has_accepted_terms", "false") == "true"
    state.is_first_launch = not state.has_accepted_terms

    def navigate(route: str):
        """Sync navigation helper using deprecated page.go() to match fletbot pattern."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            page.go(route)

    async def play_stream(url: str):
        await db_manager.save_history(url)
        state.add_to_history(url)
        encoded_url = base64.b64encode(url.encode()).decode()
        navigate(f"/play?url={encoded_url}")

    async def load_channels():
        state.is_loading = True
        page.update()
        
        # Load all sources (Built-in + Custom DB)
        all_channels = await iptv_service.load_all_sources()
        state.channels = all_channels
        
        state.is_loading = False
        page.update()

    # Expose load_channels to views
    page.load_channels = load_channels

    async def route_change(e: ft.RouteChangeEvent | None):
        page.views.clear()
        parsed_url = urllib.parse.urlparse(page.route)
        
        # Root / Splash
        if parsed_url.path == "/":
            dest = "/dashboard" if not state.is_first_launch else "/onboarding"
            page.views.append(
                ft.View("/", [SplashView(on_complete=lambda: navigate(dest))], padding=0)
            )
        
        # Onboarding
        elif parsed_url.path == "/onboarding":
            page.views.append(
                ft.View("/onboarding", [OnboardingView(on_complete=lambda: navigate("/dashboard"))], padding=0)
            )
        
        # Dashboard
        elif parsed_url.path == "/dashboard":
            page.views.append(
                ft.View("/dashboard", [DashboardView(on_play=play_stream)], padding=0)
            )
            if not state.channels:
                page.run_task(load_channels)
        
        # Player (Robust parsing)
        elif parsed_url.path == "/play":
            params = urllib.parse.parse_qs(parsed_url.query)
            encoded_url = params.get("url", [None])[0]
            if encoded_url:
                try:
                    url = base64.b64decode(encoded_url).decode()
                    page.views.append(
                        ft.View(page.route, [PlayerView(url=url, on_back=lambda: navigate("/dashboard"))], padding=0)
                    )
                except Exception as ex:
                    print(f"URL Decode Error: {ex}")
                    navigate("/dashboard")
            else:
                navigate("/dashboard")

        page.update()

    def view_pop(e: ft.ViewPopEvent):
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            navigate(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    # Initial Route
    page.route = "/"
    await route_change(None)

if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
