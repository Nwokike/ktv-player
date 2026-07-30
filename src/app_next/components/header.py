"""Header — Top Material 3 AppBar: logo + search + actions.

Built on Flet 0.86's ft.AppBar (verified .venv/.../material/app_bar.py):
- leading slot for the logo (and add button if on_add_content is set)
- title slot for the search field
- actions slot for refresh + theme toggle
- toolbar_height=48 + elevation_on_scroll=4 for a tighter, native look
"""

from collections.abc import Callable

import flet as ft
from flet import Control, context

from app_next.utils.theme_utils import toggle_theme as _toggle_theme_util
from core.constants import LBL_ADD_CONTENT, LBL_SEARCH_HINT
from core.tokens import FONT_MD, ICON_MD, ICON_SM, RADIUS_MD, SPACING_SM

_HEADER_TOOLBAR_HEIGHT = 48


@ft.component
def Header(
    search_value: str = "",
    on_search_change: Callable[[str], None] | None = None,
    on_add_content: Callable[[], None] | None = None,
    search_hint: str = LBL_SEARCH_HINT,
    add_tooltip: str = LBL_ADD_CONTENT,
    on_refresh: Callable[[], None] | None = None,
) -> Control:
    """Render the top AppBar."""

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

    _compact_style = ft.ButtonStyle(padding=ft.Padding.all(4))
    _leading_width = 88 if callable(on_add_content) else 44

    leading_controls: list[Control] = [
        ft.Image(
            src="/icon.png",
            width=28,
            height=28,
            fit=ft.BoxFit.CONTAIN,
            border_radius=RADIUS_MD,
        ),
    ]
    if callable(on_add_content):
        leading_controls.append(
            ft.IconButton(
                icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                tooltip=add_tooltip,
                on_click=lambda e: on_add_content(),
                icon_size=ICON_MD,
                style=_compact_style,
            )
        )

    actions: list[Control] = []
    if callable(on_refresh):
        actions.append(
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                tooltip="Scan Again",
                on_click=lambda e: on_refresh(),
                icon_size=ICON_SM,
                style=_compact_style,
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
            icon_size=ICON_SM,
            style=_compact_style,
        )
    )

    return ft.AppBar(
        leading=ft.Row(
            controls=leading_controls,
            spacing=2,
            tight=True,
        ),
        leading_width=_leading_width,
        title=ft.Container(content=search_field, expand=True),
        center_title=False,
        toolbar_height=_HEADER_TOOLBAR_HEIGHT,
        elevation_on_scroll=4,
        actions=actions,
    )
