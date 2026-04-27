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
    print("Starting App main...")
    page.title = "KTV Player"
    page.padding = 0
    page.spacing = 0
    page.theme_mode = ft.ThemeMode.LIGHT # Force light for debugging
    page.theme = AppTheme.get_light_theme()
    
    # Initialize Services
    lifecycle_manager = LifecycleManager(page)
    print("Initializing Database...")
    await db_manager.init_db()
    
    # Load settings from DB
    state.user_country = await db_manager.get_setting("user_country", "")
    state.has_accepted_terms = await db_manager.get_setting("has_accepted_terms", "false") == "true"
    state.is_first_launch = not state.has_accepted_terms
    print(f"First launch: {state.is_first_launch}")

    async def play_stream(url: str):
        await db_manager.save_history(url)
        state.add_to_history(url)
        encoded_url = base64.b64encode(url.encode()).decode()
        await page.push_route(f"/play?url={encoded_url}")

    async def load_channels():
        state.is_loading = True
        page.update()
        all_channels = await iptv_service.load_all_sources()
        state.channels = all_channels
        state.is_loading = False
        page.update()

    async def route_change(e):
        print(f"Route changed to: {page.route}")
        page.views.clear()
        
        # We always need a base view as per recommendations
        if page.route == "/" or page.route == "":
            dest = "/dashboard" if not state.is_first_launch else "/onboarding"
            
            # Use a simpler view structure
            page.views.append(
                ft.View(
                    "/",
                    [SplashView()],
                    padding=0,
                    bgcolor=ft.Colors.WHITE,
                    vertical_alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
            
            async def splash_timeout():
                await asyncio.sleep(3)
                print(f"Navigating to {dest}")
                await page.push_route(dest)
            
            page.run_task(splash_timeout)

        elif page.route == "/onboarding":
            async def on_onboarding_complete():
                await page.push_route("/dashboard")

            page.views.append(
                ft.View(
                    "/onboarding",
                    [OnboardingView(on_complete=on_onboarding_complete)],
                    padding=0,
                    bgcolor=ft.Colors.WHITE,
                    vertical_alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        elif page.route == "/dashboard":
            page.views.append(
                ft.View(
                    "/dashboard",
                    [DashboardView(on_play=play_stream)],
                    padding=0,
                    bgcolor=ft.Colors.WHITE,
                )
            )
            if not state.channels:
                page.run_task(load_channels)

        elif page.route.startswith("/play"):
            # Simplified for now
            page.views.append(
                ft.View(
                    page.route,
                    [ft.Text("Player Loading...")],
                    bgcolor=ft.Colors.BLACK,
                )
            )

        page.update()

    async def view_pop(e):
        page.views.pop()
        top_view = page.views[-1]
        await page.push_route(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    
    # Trigger initial route
    print(f"Initial route: {page.route}")
    if page.route == "/" or page.route == "":
        await route_change(None)
    else:
        await page.push_route(page.route)
    page.update()

if __name__ == "__main__":
    print("Executing ft.run(main)...")
    ft.run(main, assets_dir="assets")
