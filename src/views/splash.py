import flet as ft
from core.theme import AppColors


def build_splash_view() -> ft.View:
    return ft.View(
        route="/",
        controls=[
            ft.Container(
                content=ft.Column(
                    [
                        ft.Image(
                            src="/icon.png",
                            width=100,
                            height=100,
                            border_radius=15,
                        ),
                        ft.Text(
                            "KTV PLAYER", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE
                        ),
                        ft.Text("High-Speed Streaming Engine", color=ft.Colors.WHITE_70),
                        ft.Container(height=20),
                        ft.ProgressBar(
                            width=240, color=AppColors.PRIMARY, bgcolor=ft.Colors.WHITE_24
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                expand=True,
                alignment=ft.Alignment(0, 0),
                bgcolor=AppColors.SPLASH_BG,
            )
        ],
        padding=0,
    )
