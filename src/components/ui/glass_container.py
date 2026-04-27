import flet as ft
from core.theme import AppColors

class GlassContainer(ft.Container):
    def __init__(
        self,
        content: ft.Control,
        padding: float = 20,
        border_radius: float = 20,
        expand: bool = False,
        on_click: callable = None,
    ):
        super().__init__()
        self.content = content
        self.padding = padding
        self.border_radius = border_radius
        self.bgcolor = ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE)
        self.border = ft.border.all(0.5, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))
        self.blur = ft.Blur(10, 10, ft.BlurTileMode.MIRROR)
        self.expand = expand
        self.on_click = on_click
        self.animate = ft.animation.Animation(300, ft.AnimationCurve.DECELERATE)
