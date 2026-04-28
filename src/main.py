import flet as ft
from core.theme import AppTheme
from core.state import state
from services.iptv_service import iptv_service
from services.lifecycle import LifecycleManager
from database.manager import db_manager
from views.splash import build_splash_view
from views.dashboard import build_dashboard_view
from views.player_view import build_player_view
from views.onboarding import build_onboarding_view
import base64
import urllib.parse
import asyncio

async def main(page: ft.Page):
    page.title = "KTV Player"
    page.favicon = "icon.png"
    
    # Load premium typography
    page.fonts = {
        "Outfit": "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap"
    }
    
    page.theme = AppTheme.get_light_theme()
    page.dark_theme = AppTheme.get_dark_theme()
    page.theme.font_family = "Outfit"
    page.dark_theme.font_family = "Outfit"
    
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

    async def navigate(route: str):
        """Async navigation helper."""
        await page.push_route(route)

    async def play_stream(url: str):
        await db_manager.save_history(url)
        state.add_to_history(url)
        # Use urlsafe base64 to avoid issues with + and /
        encoded_url = base64.urlsafe_b64encode(url.encode()).decode()
        await navigate(f"/play?url={encoded_url}")

    async def load_channels():
        state.is_loading = True
        page.update()
        all_channels = await iptv_service.load_all_sources()
        state.channels = all_channels
        state.is_loading = False
        page.update()

    async def start_splash_timer():
        """Handles the splash screen timeout."""
        await asyncio.sleep(3)
        dest = "/dashboard" if not state.is_first_launch else "/onboarding"
        await navigate(dest)

    # Expose load_channels to views
    page.load_channels = load_channels

    async def route_change(e: ft.RouteChangeEvent | None = None):
        route = page.route
        parsed_url = urllib.parse.urlparse(route)
        
        # Only clear stack for root-level navigations
        if parsed_url.path in ["/", "/dashboard", "/onboarding"]:
            page.views.clear()
        
        if parsed_url.path == "/":
            page.views.append(build_splash_view())
            page.run_task(start_splash_timer)
        
        elif parsed_url.path == "/onboarding":
            page.views.append(build_onboarding_view(on_complete=lambda: page.run_task(navigate, "/dashboard")))
        
        elif parsed_url.path == "/dashboard":
            page.views.append(build_dashboard_view(page=page, on_play=play_stream))
            if not state.channels:
                page.run_task(load_channels)
        
        elif parsed_url.path == "/play":
            params = urllib.parse.parse_qs(parsed_url.query)
            encoded_url = params.get("url", [None])[0]
            if encoded_url:
                try:
                    # Dynamically pad the Base64 string to prevent padding errors on deep links
                    padding = '=' * (-len(encoded_url) % 4)
                    padded_url = encoded_url + padding
                    url = base64.urlsafe_b64decode(padded_url).decode()
                    page.views.append(build_player_view(url=url, on_back=lambda: page.run_task(navigate, "/dashboard")))
                except Exception as ex:
                    print(f"Deep link decode error: {ex}")
                    page.run_task(navigate, "/dashboard")
            else:
                page.run_task(navigate, "/dashboard")

        page.update()

    def view_pop(e: ft.ViewPopEvent):
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            page.run_task(navigate, top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    # Initial Route
    await route_change()

if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
