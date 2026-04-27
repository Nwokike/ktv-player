import flet as ft
import asyncio
from core.theme import AppColors

class SplashView(ft.Container):
    def __init__(self, on_complete: callable):
        super().__init__()
        self.on_complete = on_complete
        self.expand = True
        self.alignment = ft.Alignment(0, 0)
        self.bgcolor = ft.Colors.SURFACE
        
        self.logo = ft.Image(
            src="icon.png",
            width=150,
            height=150,
            fit=ft.BoxFit.CONTAIN,
        )
        
        self.content = ft.Column([
            self.logo,
            ft.Text("KTV PLAYER", style=ft.TextThemeStyle.HEADLINE_LARGE, color=AppColors.PRIMARY),
            ft.Text("Immersive High-Speed Rendering", color=ft.Colors.ON_SURFACE_VARIANT),
            ft.ProgressBar(width=200, color=AppColors.SECONDARY, bgcolor=ft.Colors.SURFACE_CONTAINER),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)

    def did_mount(self):
        # Start the animation timer when added to page
        self.page.run_task(self.animate_splash)

    async def animate_splash(self):
        await asyncio.sleep(3)
        if asyncio.iscoroutinefunction(self.on_complete):
            await self.on_complete()
        else:
            self.on_complete()
