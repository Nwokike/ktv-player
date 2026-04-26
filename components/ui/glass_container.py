import flet as ft
from core.theme import AppColors

@ft.component
def GlassContainer(
    content: ft.Control,
    padding: float = 20,
    border_radius: float = 20,
    expand: bool = False,
    on_click: callable = None,
):
    return ft.Container(
        content=content,
        padding=padding,
        border_radius=border_radius,
        bgcolor=AppColors.GLASS_BG,
        border=ft.border.all(0.5, AppColors.GLASS_BORDER),
        blur=ft.Blur(10, 10, ft.BlurStyle.OUTER),
        expand=expand,
        on_click=on_click,
        animate=ft.animation.Animation(300, ft.AnimationCurve.DECELERATE),
    )
