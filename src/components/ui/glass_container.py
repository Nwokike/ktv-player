from collections.abc import Callable

import flet as ft

from core.theme import AppColors

_ANIM_SCALE = ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_OUT)
_ANIM_BG = ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_OUT)
_DEFAULT_BORDER = ft.Border.all(0.5, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE))
_FOCUS_BORDER = ft.Border.all(2.5, AppColors.PRIMARY)
_DEFAULT_BG = ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE)
_FOCUS_BG = ft.Colors.with_opacity(0.1, AppColors.PRIMARY)
_FOCUS_SHADOW = ft.BoxShadow(
    spread_radius=4,
    blur_radius=20,
    color=ft.Colors.with_opacity(0.3, AppColors.PRIMARY),
    offset=ft.Offset(0, 6),
)


class GlassContainer(ft.Container):
    def __init__(
        self,
        content: ft.Control = None,
        padding: float = 16,
        border_radius: float = 20,
        expand: bool = False,
        on_click: Callable | None = None,
        focusable: bool = False,
        key: str | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.content = content
        self.padding = padding
        self.border_radius = border_radius
        self.key = key

        self.bgcolor = _DEFAULT_BG
        self.border = _DEFAULT_BORDER

        self.animate_scale = _ANIM_SCALE
        self.animate = _ANIM_BG

        self.expand = expand
        self.on_click = on_click

        if focusable:
            self.tab_index = 0
            self.on_focus = self._handle_focus
            self.on_blur = self._handle_blur

    def _handle_focus(self, e):
        self.border = _FOCUS_BORDER
        self.scale = 1.06
        self.bgcolor = _FOCUS_BG
        self.shadow = _FOCUS_SHADOW
        self.update()

    def _handle_blur(self, e):
        self.border = _DEFAULT_BORDER
        self.scale = 1.0
        self.bgcolor = _DEFAULT_BG
        self.shadow = None
        self.update()
