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
import asyncio

async def main(page: ft.Page):
    print("Starting App (Simple Mode)...")
    page.title = "KTV Player"
    page.theme = AppTheme.get_light_theme()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.spacing = 0
    
    await db_manager.init_db()
    state.has_accepted_terms = await db_manager.get_setting("has_accepted_terms", "false") == "true"
    state.is_first_launch = not state.has_accepted_terms

    # 1. Show Splash directly
    print("Showing Splash...")
    splash = SplashView()
    page.add(splash)
    page.update()
    
    await asyncio.sleep(3)
    
    # 2. Transition
    print("Transitioning...")
    page.clean()
    
    if state.is_first_launch:
        print("Showing Onboarding...")
        async def on_onboarding_complete():
            page.clean()
            page.add(DashboardView(on_play=lambda url: print(f"Play {url}")))
            page.update()
            
        page.add(OnboardingView(on_complete=on_onboarding_complete))
    else:
        print("Showing Dashboard...")
        page.add(DashboardView(on_play=lambda url: print(f"Play {url}")))
    
    page.update()

if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
