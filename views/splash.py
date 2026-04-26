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

    # Use a high-quality "Play" or "TV" animation
    lottie_anim = Lottie(
        src="https://lottie.host/7901309d-f203-455b-867c-9b87f9d8502f/Y0I6v3mK3R.json", # Modern Media Icon
        width=250,
        height=250,
        animate=True,
        repeat=True,
    )

    # Start the timer when the component is added
    ft.page_task(animate_splash())

    return ft.Container(
        content=ft.Column([
            lottie_anim,
            ft.Text("KTV PLAYER", style=ft.TextThemeStyle.HEADLINE_LARGE, color=AppColors.PRIMARY),
            ft.Text("Immersive High-Speed Rendering", color=AppColors.TEXT_SECONDARY),
            ft.ProgressBar(width=200, color=AppColors.SECONDARY, bgcolor=AppColors.SURFACE),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20),
        alignment=ft.alignment.center,
        expand=True,
        bgcolor=AppColors.BACKGROUND,
    )
