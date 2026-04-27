import flet as ft
from core.theme import AppColors

@ft.component
def ChannelCardShimmer():
    return ft.Shimmer(
        color=ft.colors.SURFACE_VARIANT,
        highlight_color=ft.colors.SURFACE,
        content=ft.Container(
            height=80,
            padding=15,
            border_radius=15,
            content=ft.Row([
                ft.Container(width=50, height=50, border_radius=10, bgcolor=ft.colors.SURFACE),
                ft.Column([
                    ft.Container(width=150, height=15, border_radius=5, bgcolor=ft.colors.SURFACE),
                    ft.Container(width=100, height=10, border_radius=5, bgcolor=ft.colors.SURFACE),
                ], spacing=10, expand=True)
            ])
        )
    )

@ft.component
def ShimmerList(count: int = 5):
    return ft.Column([ChannelCardShimmer() for _ in range(count)], spacing=10)
