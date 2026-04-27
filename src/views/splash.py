import flet as ft
import asyncio

def build_splash_view() -> ft.View:
    """Builds the splash screen view with minimal logic for diagnosis."""
    
    return ft.View(
        route="/",
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Image(
                        src="/icon.png",
                        width=200,
                        height=200,
                        fit=ft.BoxFit.CONTAIN,
                    ),
                    ft.Text(
                        "Immersive High-Speed Rendering", 
                        color=ft.Colors.WHITE_70
                    ),
                    ft.Container(height=20),
                    ft.ProgressBar(
                        width=200, 
                        color=ft.Colors.WHITE, 
                        bgcolor=ft.Colors.WHITE_24
                    ),
                ], 
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20),
                expand=True,
                alignment=ft.Alignment(0, 0),
                bgcolor=ft.Colors.BLUE_GREY_900, # Use a fixed dark color for contrast
            )
        ],
        padding=0,
    )

