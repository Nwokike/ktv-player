"""Header — Sleek cinematic top bar with branding and action icons."""

from collections.abc import Callable

import flet as ft
from flet import Control, context

from core.constants import APP_NAME
from utils.theme_utils import toggle_theme as _toggle_theme_util


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

    def _handle_toggle_theme(e):
        _toggle_theme_util(context.page)
        set_current_theme(getattr(context.page, "theme_mode", ft.ThemeMode.DARK))

    actions: list[Control] = []

    if callable(on_search_click):
        actions.append(
            ft.IconButton(
                icon=ft.Icons.SEARCH_ROUNDED,
                tooltip="Search",
                autofocus=True,
                on_click=lambda e: on_search_click(),
            )
        )

    if callable(on_favorites_toggle):
        from core.theme import AppColors

        fav_color = AppColors.PRIMARY if fav_active else AppColors.grey_dim()
        actions.append(
            ft.IconButton(
                icon=ft.Icons.STAR_ROUNDED
                if fav_active
                else ft.Icons.STAR_BORDER_ROUNDED,
                icon_color=fav_color,
                tooltip="Favorites",
                on_click=lambda e: on_favorites_toggle(),
            )
        )

    if callable(on_add_content):
        actions.append(
            ft.IconButton(
                icon=ft.Icons.ADD_ROUNDED,
                tooltip="Add Content",
                on_click=lambda e: on_add_content(),
            )
        )

    if callable(on_refresh):
        actions.append(
            ft.IconButton(
                icon=ft.Icons.REFRESH_ROUNDED,
                tooltip="Refresh",
                on_click=lambda e: on_refresh(),
            )
        )

    try:
        from core.theme import AppColors

        is_dark = AppColors._is_dark(context.page)
    except Exception:
        is_dark = True

    theme_icon = ft.Icons.DARK_MODE_ROUNDED if is_dark else ft.Icons.LIGHT_MODE_ROUNDED
    tooltip_text = (
        "Dark Mode (click for Light)" if is_dark else "Light Mode (click for Dark)"
    )
    actions.append(
        ft.IconButton(
            icon=theme_icon,
            tooltip=tooltip_text,
            on_click=_handle_toggle_theme,
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
                ft.Row(controls=actions),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
    )
