import flet as ft
from flet_lottie import Lottie
import asyncio
from core.theme import AppColors

def SplashView(on_complete: callable):
    # This view will display a Lottie animation for 3 seconds then call on_complete
    
    # Use the official logo
    logo = ft.Image(
        src="icon.png",
        width=150,
        height=150,
        fit="contain",
    )

    async def animate_splash(e):
        await asyncio.sleep(3)
        await on_complete()

    return ft.Container(
        content=ft.Column([
            logo,
            ft.Text("KTV PLAYER", style=ft.TextThemeStyle.HEADLINE_LARGE, color=AppColors.PRIMARY),
            ft.Text("Immersive High-Speed Rendering", color="on_surface_variant"),
            ft.ProgressBar(width=200, color=AppColors.SECONDARY, bgcolor="surface_variant"),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20),
        alignment=ft.Alignment(0, 0),
        expand=True,
        bgcolor="background",
        on_mount=lambda e: e.page.run_task(animate_splash(e))
    )
