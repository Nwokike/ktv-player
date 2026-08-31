"""Header — Sleek cinematic top bar with branding and ink-enabled action icons."""

from collections.abc import Callable

import flet as ft
from flet import Control, context

from core.constants import APP_VERSION
from core.state import state as core_state
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
    on_search_click: Callable[[], None] | None = None,
    on_favorites_toggle: Callable[[], None] | None = None,
    on_add_content: Callable[[], None] | None = None,
    on_refresh: Callable[[], None] | None = None,
    on_version_click: Callable[[], None] | None = None,
    refresh_tooltip: str = "Refresh",
    fav_active: bool = False,
    show_search: bool = True,
) -> Control:

    _current_theme, set_current_theme = ft.use_state(
        lambda: getattr(context.page, "theme_mode", ft.ThemeMode.DARK)
    )

    def _handle_toggle_theme():
        _toggle_theme_util(context.page)
        set_current_theme(getattr(context.page, "theme_mode", ft.ThemeMode.DARK))

    def _build_version_chip() -> Control | None:
        """Sherlock-style version chip: shows the current version normally,
        flips to an Update pill when a newer build is found. Always opens
        the version dialog (changelog when up to date)."""
        if not callable(on_version_click):
            return None
        update_available = core_state.update_available
        if update_available:
            update_data = core_state.update_data or {}
            label = (
                update_data.get("version", "Update")
                if update_data.get("type") != "announcement"
                else "News"
            )
            content = ft.Row(
                controls=[
                    ft.Text(
                        f"Update: {label} Available!"
                        if update_data.get("type") != "announcement"
                        else "News",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=AppColors.PRIMARY,
                        no_wrap=True,
                    ),
                    ft.Container(
                        width=6,
                        height=6,
                        border_radius=3,
                        bgcolor=AppColors.PRIMARY,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
            return ft.Container(
                content=content,
                padding=ft.Padding(10, 4, 10, 4),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.15, AppColors.PRIMARY),
                border=ft.Border.all(1.5, AppColors.PRIMARY),
                ink=True,
                tooltip="New update available — tap to view",
                on_click=lambda e: on_version_click(),
            )
        return ft.Container(
            content=ft.Text(
                f"v{APP_VERSION}",
                size=11,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE_VARIANT,
                no_wrap=True,
            ),
            padding=ft.Padding(10, 4, 10, 4),
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE_VARIANT),
            ink=True,
            tooltip="What's New — version & changelog",
            on_click=lambda e: on_version_click(),
        )

    actions: list[Control] = []

    if show_search and callable(on_search_click):
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
                tooltip=refresh_tooltip,
            )
        )

    version_chip = _build_version_chip()
    if version_chip is not None:
        actions.append(version_chip)

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
                    src="/icon.svg",
                    width=38,
                    height=38,
                    color=ft.Colors.ON_SURFACE,
                ),
            ),
        ],
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
