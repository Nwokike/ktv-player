"""Header — Top Material 3 AppBar with search + actions."""

from collections.abc import Callable

import flet as ft
from flet import Control, context

from app_next.utils.theme_utils import toggle_theme as _toggle_theme_util
from core.constants import LBL_SEARCH_HINT


@ft.component
def Header(
    search_value: str = "",
    on_search_change: Callable[[str], None] | None = None,
    on_add_content: Callable[[], None] | None = None,
    search_hint: str = LBL_SEARCH_HINT,
    on_refresh: Callable[[], None] | None = None,
) -> Control:

    def _handle_toggle_theme(e):
        _toggle_theme_util(context.page)

    search_bar = ft.SearchBar(
        value=search_value,
        bar_hint_text=search_hint,
        bar_leading=ft.Icon(ft.Icons.SEARCH),
        expand=True,
        on_change=lambda e: (
            on_search_change(e.control.value) if callable(on_search_change) else None
        ),
    )

    leading_controls: list[Control] = [
        ft.Image(src="/icon.png"),
    ]

    actions: list[Control] = []
    if callable(on_refresh):
        actions.append(
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                tooltip="Scan Again",
                on_click=lambda e: on_refresh(),
            )
        )
    try:
        from core.theme import AppColors

        is_dark = AppColors._is_dark(context.page)
    except Exception:
        is_dark = True
    theme_icon = ft.Icons.DARK_MODE if is_dark else ft.Icons.LIGHT_MODE
    actions.append(
        ft.IconButton(
            icon=theme_icon,
            tooltip="Toggle Theme",
            on_click=_handle_toggle_theme,
        )
    )

    return ft.AppBar(
        leading=ft.Row(
            controls=leading_controls,
            tight=True,
        ),
        title=ft.Container(
            content=search_bar,
            expand=True,
            alignment=ft.Alignment.CENTER,
        ),
        center_title=True,
        elevation_on_scroll=4,
        actions=actions,
    )
