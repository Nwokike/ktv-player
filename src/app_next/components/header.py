"""Header — Top-level header component with App logo, inline search bar, and action buttons."""

from collections.abc import Callable

import flet as ft
from flet.controls.context import context
from flet.controls.control import Control

from app_next.utils.theme_utils import toggle_theme as _toggle_theme_util
from core.constants import LBL_ADD_CONTENT, LBL_SEARCH_HINT
from core.tokens import FONT_MD, ICON_MD, ICON_SM, RADIUS_MD, SPACING_MD, SPACING_SM


@ft.component
def Header(
    search_value: str = "",
    on_search_change: Callable[[str], None] | None = None,
    on_add_content: Callable[[], None] | None = None,
    search_hint: str = LBL_SEARCH_HINT,
    add_tooltip: str = LBL_ADD_CONTENT,
    on_refresh: Callable[[], None] | None = None,
) -> Control:
    """Render top bar with App Icon, Search Bar, Add Button (+), optional Refresh, and Theme Toggle."""

    def _handle_toggle_theme(e):
        _toggle_theme_util(context.page)

    search_field = ft.TextField(
        value=search_value,
        hint_text=search_hint,
        on_change=lambda e: (
            on_search_change(e.control.value) if callable(on_search_change) else None
        ),
        prefix_icon=ft.Icons.SEARCH,
        dense=True,
        text_size=FONT_MD,
        content_padding=ft.Padding(SPACING_SM, 6, SPACING_SM, 6),
        border_radius=RADIUS_MD,
        expand=True,
    )

    action_controls = [
        ft.IconButton(
            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
            tooltip=add_tooltip,
            on_click=lambda e: on_add_content() if callable(on_add_content) else None,
            icon_size=ICON_MD,
        )
    ]

    if callable(on_refresh):
        action_controls.append(
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                tooltip="Scan Again",
                on_click=lambda e: on_refresh(),
                icon_size=ICON_SM,
            )
        )

    # Dynamic Theme Icon
    try:
        page_theme = context.page.theme_mode
        is_dark = page_theme == ft.ThemeMode.DARK
    except Exception:
        is_dark = True

    theme_icon = ft.Icons.LIGHT_MODE if is_dark else ft.Icons.DARK_MODE

    action_controls.append(
        ft.IconButton(
            icon=theme_icon,
            tooltip="Toggle Theme",
            on_click=_handle_toggle_theme,
            icon_size=ICON_SM,
        )
    )

    actions_row = ft.Row(
        controls=action_controls,
        spacing=0,
        tight=True,
    )

    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Image(
                    src="/icon.png",
                    width=32,
                    height=32,
                    fit=ft.BoxFit.CONTAIN,
                    border_radius=RADIUS_MD,
                ),
                search_field,
                actions_row,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=SPACING_SM,
        ),
        padding=ft.Padding(SPACING_MD, SPACING_SM, SPACING_MD, 4),
    )
