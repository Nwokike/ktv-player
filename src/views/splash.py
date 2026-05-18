import flet as ft

from core.theme import AppColors


def build_splash_view(page: ft.Page) -> ft.View:
    is_dark = AppColors._is_dark(page)
    bg = AppColors.DARK_BG if is_dark else AppColors.LIGHT_BG
    text = AppColors.DARK_TEXT if is_dark else AppColors.LIGHT_TEXT
    text_dim = AppColors.DARK_TEXT_DIM if is_dark else AppColors.LIGHT_TEXT_DIM

    return ft.View(
        route="/",
        controls=[
            ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Image(
                                src="/icon.png",
                                width=110,
                                height=110,
                                border_radius=22,
                            ),
                            border_radius=22,
                        ),
                        ft.Container(height=24),
                        ft.Text(
                            "KTV PLAYER",
                            size=28,
                            weight=ft.FontWeight.BOLD,
                            color=text,
                        ),
                        ft.Text(
                            "High-Speed Streaming Engine",
                            size=13,
                            color=text_dim,
                        ),
                        ft.Container(height=32),
                        ft.ProgressBar(
                            width=220,
                            color=AppColors.PRIMARY,
                            bgcolor=ft.Colors.with_opacity(0.15, text_dim),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=0,
                ),
                expand=True,
                alignment=ft.Alignment(0, 0),
                bgcolor=bg,
            )
        ],
        padding=0,
    )
