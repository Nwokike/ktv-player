import contextlib

import flet as ft

from core.constants import (
    FOCUS_ANIM_DURATION,
    FOCUS_ANIM_SHORT,
    FOCUS_BORDER_WIDTH,
    FOCUS_SCALE,
)
from core.theme import AppColors

PRIMARY_COLOR = AppColors.PRIMARY

_tab_index_counter = 0


def next_tab_index() -> int:
    """Return a globally unique, sequentially increasing tab_index."""
    global _tab_index_counter
    _tab_index_counter += 1
    return _tab_index_counter


def reset_tab_counter():
    global _tab_index_counter
    _tab_index_counter = 0


class FocusManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self._back_handler = None
        page.on_keyboard_event = self._handle_keyboard

    def set_back_handler(self, handler: callable):
        self._back_handler = handler

    def _handle_keyboard(self, e: ft.KeyboardEvent):
        if e.key in ("Escape", "Back", "BrowserBack", "Go Back") and self._back_handler:
            self._back_handler()


def apply_focus_scale(control: ft.Container, focused: bool):
    if focused:
        control.scale = FOCUS_SCALE
        control.border = ft.Border.all(FOCUS_BORDER_WIDTH, PRIMARY_COLOR)
        control.shadow = ft.BoxShadow(
            spread_radius=5,
            blur_radius=25,
            color=ft.Colors.with_opacity(0.5, PRIMARY_COLOR),
            offset=ft.Offset(0, 10),
        )
    else:
        control.scale = 1.0
        control.border = ft.Border.all(0, ft.Colors.TRANSPARENT)
        control.shadow = None
    with contextlib.suppress(Exception):
        control.update()


def apply_focus_border(control: ft.Container, focused: bool):
    if focused:
        control.bgcolor = ft.Colors.with_opacity(0.12, PRIMARY_COLOR)
        control.border = ft.Border.all(2.5, PRIMARY_COLOR)
    else:
        control.bgcolor = None
        control.border = ft.Border.all(1.5, PRIMARY_COLOR)
    with contextlib.suppress(Exception):
        control.update()


def apply_focus_btn(control: ft.Container, focused: bool):
    if focused:
        control.bgcolor = ft.Colors.with_opacity(0.15, PRIMARY_COLOR)
        control.scale = 1.05
    else:
        control.bgcolor = None
        control.scale = 1.0
    with contextlib.suppress(Exception):
        control.update()


def make_focusable_card(control: ft.Container):
    control.on_focus = lambda e: apply_focus_scale(e.control, True)
    control.on_blur = lambda e: apply_focus_scale(e.control, False)
    control.animate_scale = ft.Animation(
        FOCUS_ANIM_DURATION, ft.AnimationCurve.EASE_OUT
    )
    control.animate = ft.Animation(FOCUS_ANIM_DURATION, ft.AnimationCurve.EASE_OUT)


def make_focusable_button(control: ft.Container):
    control.on_focus = lambda e: apply_focus_btn(e.control, True)
    control.on_blur = lambda e: apply_focus_btn(e.control, False)
    control.animate_scale = ft.Animation(FOCUS_ANIM_SHORT, ft.AnimationCurve.EASE_OUT)


def make_focusable_border(control: ft.Container):
    control.on_focus = lambda e: apply_focus_border(e.control, True)
    control.on_blur = lambda e: apply_focus_border(e.control, False)
