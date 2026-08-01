"""Header — Sleek cinematic top bar with branding and ink-enabled action icons."""

from collections.abc import Callable

import flet as ft
from flet import Control, context

from core.constants import APP_NAME
from core.theme import AppColors
from utils.theme_utils import toggle_theme as _toggle_theme_util


def _make_icon_btn(
    icon: str,
    on_click: Callable[[], None],
    tooltip: str = "",
    icon_color: str | None = None,
) -> Control:
    """Helper to build an ink-enabled icon button with exact original design."""
    return ft.Container(
        content=ft.Icon(
            icon,
            size=20,
            color=icon_color if icon_color else ft.Colors.ON_SURFACE,
        ),
        padding=8,
        border_radius=8,
        ink=True,
        tooltip=tooltip,
        on_click=lambda e: on_click(),
    )


@ft.component
def Header(
    title: str = APP_NAME,
    on_search_click: Callable[[], None] | None = None,
    on_favorites_toggle: Callable[[], None] | None = None,
    on_add_content: Callable[[], None] | None = None,
    on_refresh: Callable[[], None] | None = None,
    fav_active: bool = False,
) -> Control:

    _current_theme, set_current_theme = ft.use_state(
        lambda: getattr(context.page, "theme_mode", ft.ThemeMode.DARK)
    )

    def _handle_toggle_theme():
        _toggle_theme_util(context.page)
        set_current_theme(getattr(context.page, "theme_mode", ft.ThemeMode.DARK))

    actions: list[Control] = []

    if callable(on_search_click):
        actions.append(
            _make_icon_btn(
                icon=ft.Icons.SEARCH_ROUNDED,
                on_click=on_search_click,
                tooltip="Search",
            )
        )

    if callable(on_favorites_toggle):
        fav_color = AppColors.PRIMARY if fav_active else None
        actions.append(
            _make_icon_btn(
                icon=ft.Icons.STAR_ROUNDED
                if fav_active
                else ft.Icons.STAR_BORDER_ROUNDED,
                on_click=on_favorites_toggle,
                tooltip="Favorites",
                icon_color=fav_color,
            )
        )

    if callable(on_add_content):
        actions.append(
            _make_icon_btn(
                icon=ft.Icons.ADD_ROUNDED,
                on_click=on_add_content,
                tooltip="Add Content",
            )
        )

    if callable(on_refresh):
        actions.append(
            _make_icon_btn(
                icon=ft.Icons.REFRESH_ROUNDED,
                on_click=on_refresh,
                tooltip="Refresh",
            )
        )

    try:
        is_dark = AppColors._is_dark(context.page)
    except Exception:
        is_dark = True

    theme_icon = ft.Icons.DARK_MODE_ROUNDED if is_dark else ft.Icons.LIGHT_MODE_ROUNDED
    tooltip_text = (
        "Dark Mode (click for Light)" if is_dark else "Light Mode (click for Dark)"
    )
    actions.append(
        _make_icon_btn(
            icon=theme_icon,
            on_click=_handle_toggle_theme,
            tooltip=tooltip_text,
        )
    )

    brand_row = ft.Row(
        controls=[
            ft.Container(
                content=ft.Image(
                    src="/icon.png", width=32, height=32, fit=ft.BoxFit.CONTAIN
                ),
                border_radius=8,
            ),
            ft.Text(title, size=20, weight=ft.FontWeight.BOLD),
        ],
        spacing=10,
        alignment=ft.MainAxisAlignment.START,
    )

    return ft.Container(
        padding=ft.Padding.only(left=24, right=24, top=24, bottom=8),
        content=ft.Row(
            controls=[
                brand_row,
                ft.Row(controls=actions, spacing=4),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
    )
