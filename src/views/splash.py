import flet as ft
from flet_lottie import Lottie
import asyncio
from core.theme import AppColors

@ft.component
def SplashView(on_complete: callable):
    # This view will display a Lottie animation for 3 seconds then call on_complete
    
    async def animate_splash():
        await asyncio.sleep(3)
        await on_complete()

    # Use the official logo
    logo = ft.Image(
        src="icon.png",
        width=150,
        height=150,
        fit=ft.ImageFit.CONTAIN,
    )

    # Start the timer when the component is added
    ft.page_task(animate_splash())

    return ft.Container(
        content=ft.Column([
            logo,
            ft.Text("KTV PLAYER", style=ft.TextThemeStyle.HEADLINE_LARGE, color=AppColors.PRIMARY),
            ft.Text("Immersive High-Speed Rendering", color=ft.colors.ON_SURFACE_VARIANT),
            ft.ProgressBar(width=200, color=AppColors.SECONDARY, bgcolor=ft.colors.SURFACE_VARIANT),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20),
        alignment=ft.alignment.center,
        expand=True,
        bgcolor=ft.colors.BACKGROUND,
    )
