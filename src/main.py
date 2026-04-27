import flet as ft
from core.theme import AppTheme
from core.state import state
from services.iptv_service import iptv_service
from services.lifecycle import LifecycleManager
from database.manager import db_manager
from views.splash import SplashView
from views.dashboard import DashboardView
from views.player_view import PlayerView
from views.onboarding import OnboardingView
import base64
import urllib.parse
import asyncio

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

    async def navigate(route: str):
        await page.push_route(route)

    async def play_stream(url: str):
        await db_manager.save_history(url)
        state.add_to_history(url)
        encoded_url = base64.b64encode(url.encode()).decode()
        await navigate(f"/play?url={encoded_url}")

    async def load_channels():
        state.is_loading = True
        page.update()
        all_channels = await iptv_service.load_all_sources()
        state.channels = all_channels
        state.is_loading = False
        page.update()

    async def route_change(e: ft.RouteChangeEvent):
        print(f"Route changing to: {page.route}")
        page.views.clear()
        parsed_url = urllib.parse.urlparse(page.route)
        
        # Root / Splash
        if parsed_url.path == "/" or parsed_url.path == "":
            dest = "/dashboard" if not state.is_first_launch else "/onboarding"
            page.views.append(
                ft.View("/", [SplashView()], padding=0, bgcolor=ft.Colors.WHITE)
            )
            
            async def splash_timeout():
                await asyncio.sleep(3)
                print(f"Splash timeout. Navigating to {dest}")
                await page.push_route(dest)
                
            page.run_task(splash_timeout)
        
        # Onboarding
        elif parsed_url.path == "/onboarding":
            async def on_onboarding_complete():
                await page.push_route("/dashboard")

            page.views.append(
                ft.View("/onboarding", [OnboardingView(on_complete=on_onboarding_complete)], padding=0, bgcolor=ft.Colors.WHITE)
            )
        
        # Dashboard
        elif parsed_url.path == "/dashboard":
            page.views.append(
                ft.View("/dashboard", [DashboardView(on_play=play_stream)], padding=0, bgcolor=ft.Colors.WHITE)
            )
            if not state.channels:
                page.run_task(load_channels)

        # Player
        elif parsed_url.path == "/play":
            params = urllib.parse.parse_qs(parsed_url.query)
            encoded_url = params.get("url", [None])[0]
            if encoded_url:
                try:
                    url = base64.b64decode(encoded_url).decode()
                    async def on_player_back():
                        await page.push_route("/dashboard")
                    page.views.append(
                        ft.View(page.route, [PlayerView(url=url, on_back=on_player_back)], padding=0, bgcolor=ft.Colors.BLACK)
                    )
                except:
                    await page.push_route("/dashboard")
            else:
                await page.push_route("/dashboard")

        page.update()

    async def view_pop(e: ft.ViewPopEvent):
        page.views.pop()
        top_view = page.views[-1]
        await page.push_route(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    if page.route == "/":
        await route_change(None)
    else:
        await page.push_route(page.route)
    page.update()

if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
