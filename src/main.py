import flet as ft
import base64
import urllib.parse
import asyncio

from core.theme import AppTheme, AppColors
from core.state import state
from services.iptv_service import iptv_service
from services.lifecycle import LifecycleManager
from services.ad_service import AdService
from database.manager import db_manager
from views.splash import build_splash_view
from views.dashboard import build_dashboard_view
from views.player_view import build_player_view
from views.onboarding import build_onboarding_view


async def main(page: ft.Page):
    page.title = "KTV Player"
    page.favicon = "icon.png"

    def global_error_handler(e):
        print(f"Caught Flet Engine Error: {e.data}")
        page.snack_bar = ft.SnackBar(
            ft.Text("Stream unavailable or network timeout."), bgcolor=AppColors.WARNING
        )
        page.snack_bar.open = True
        page.update()

    page.on_error = global_error_handler

    page.fonts = {
        "Outfit": "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap"
    }
    page.theme = AppTheme.get_light_theme()
    page.dark_theme = AppTheme.get_dark_theme()
    page.theme.font_family = "Outfit"
    page.dark_theme.font_family = "Outfit"
    page.theme_mode = ft.ThemeMode.SYSTEM
    state.theme_mode = page.theme_mode
    page.padding = 0
    page.spacing = 0

    ad_service = AdService(page)
    page.run_task(ad_service.preload_interstitial)

    lifecycle_manager = LifecycleManager(page)
    await db_manager.init_db()

    state.user_country = await db_manager.get_setting("user_country", "")
    state.has_accepted_terms = await db_manager.get_setting("has_accepted_terms", "false") == "true"
    state.is_first_launch = not state.has_accepted_terms

    async def navigate(route: str):
        await page.push_route(route)

    async def play_stream(url: str):
        # 1. Show an instant tactile loading spinner 
        loading_dialog = ft.AlertDialog(
            modal=True,
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.ProgressRing(color=AppColors.PRIMARY, stroke_width=4),
                        ft.Text("Preparing stream...", weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    tight=True,
                    spacing=15,
                ),
                padding=20,
            ),
        )
        # FIX: Bulletproof way to open dialogs on Android
        page.dialog = loading_dialog
        loading_dialog.open = True
        page.update()

        # 2. Process data in the background
        await db_manager.save_history(url)
        state.add_to_history(url)
        encoded_url = base64.urlsafe_b64encode(url.encode()).decode()

        # 3. TRIGGER PRE-ROLL INTERSTITIAL AD
        await ad_service.show_interstitial()

        # 4. Remove spinner and navigate seamlessly
        loading_dialog.open = False
        page.update()
        await navigate(f"/play?url={encoded_url}")

    async def load_channels():
        state.is_loading = True
        if hasattr(page, "refresh_dashboard"):
            page.refresh_dashboard()
        else:
            page.update()

        all_channels = await iptv_service.load_all_sources()
        state.channels = all_channels
        state.is_loading = False

        if hasattr(page, "refresh_dashboard"):
            page.refresh_dashboard()
        else:
            page.update()

    async def start_splash_timer():
        await asyncio.sleep(3)
        dest = "/dashboard" if not state.is_first_launch else "/onboarding"
        await navigate(dest)

    page.load_channels = load_channels

    async def route_change(e: ft.RouteChangeEvent | None = None):
        route = page.route
        parsed_url = urllib.parse.urlparse(route)

        if parsed_url.path in ["/", "/dashboard", "/onboarding"]:
            page.views.clear()

        if parsed_url.path == "/":
            page.views.append(build_splash_view())
            page.run_task(start_splash_timer)

        elif parsed_url.path == "/onboarding":
            page.views.append(
                build_onboarding_view(on_complete=lambda: page.run_task(navigate, "/dashboard"))
            )

        elif parsed_url.path == "/dashboard":
            page.views.append(build_dashboard_view(page_obj=page, on_play=play_stream))
            if not state.channels:
                page.run_task(load_channels)

        elif parsed_url.path == "/play":
            params = urllib.parse.parse_qs(parsed_url.query)
            encoded_url = params.get("url", [None])[0]
            if encoded_url:
                try:
                    padding = "=" * (-len(encoded_url) % 4)
                    padded_url = encoded_url + padding
                    url = base64.urlsafe_b64decode(padded_url).decode()
                    page.views.append(
                        build_player_view(
                            url=url, on_back=lambda: page.run_task(navigate, "/dashboard")
                        )
                    )
                except Exception as ex:
                    print(f"Deep link decode error: {ex}")
                    page.run_task(navigate, "/dashboard")
            else:
                page.run_task(navigate, "/dashboard")

        page.update()

    async def view_pop(e: ft.ViewPopEvent):
        if len(page.views) > 1:
            top_view = page.views[-1]
            if top_view.route.startswith("/play"):
                for control in top_view.controls:
                    if hasattr(control, "pause"):
                        try:
                            control.pause()
                        except Exception:
                            pass

                await ad_service.show_interstitial()

            page.views.pop()
            previous_view = page.views[-1]
            await navigate(previous_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    await route_change()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
