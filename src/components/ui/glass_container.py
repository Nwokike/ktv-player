import flet as ft
from core.theme import AppColors

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
        bgcolor=ft.Colors.with_opacity(0.05, "on_surface"),
        border=ft.border.all(0.5, ft.Colors.with_opacity(0.1, "on_surface")),
        blur=ft.Blur(10, 10, ft.BlurStyle.OUTER),
        expand=expand,
        on_click=on_click,
        animate=ft.animation.Animation(300, ft.AnimationCurve.DECELERATE),
    )
