"""Header — Sleek cinematic top bar with branding and ink-enabled action icons.

Action buttons stay Containers with ink + on_click: they are reachable by
D-pad focus as-is, so swapping in IconButtons would change the measured
visuals for nothing. All action callbacks are SYNC zero-or-one-arg: Flet
dispatch tolerates both arities and the header never awaits them, so an
async callback would silently drop its coroutine — keep callbacks sync
(or schedule their own work) and they always run.
"""

from collections.abc import Callable

import flet as ft
from flet import Control, context

from core.constants import APP_VERSION
from core.state import state as core_state
from core.theme import AppColors
from utils.theme_utils import toggle_theme as _toggle_theme_util


def _invoke(callback: Callable | None, e=None) -> None:
    """Call a header action tolerating zero-arg and event-taking signatures."""
    if not callable(callback):
        return
    try:
        callback(e) if e is not None else callback()
    except TypeError:
        try:
            callback()
        except TypeError:
            callback(e)


def _make_icon_btn(
    icon: str,
    on_click: Callable[..., None],
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
        on_click=lambda e: _invoke(on_click, e),
    )


def _resolve_page():
    """context.page or None — getattr-default CANNOT catch the raise, so
    the try/except is load-bearing (off-session render must not crash)."""
    try:
        return context.page
    except RuntimeError:
        return None


@ft.component
def Header(
    on_search_click: Callable[..., None] | None = None,
    on_favorites_toggle: Callable[..., None] | None = None,
    on_add_content: Callable[..., None] | None = None,
    on_refresh: Callable[..., None] | None = None,
    on_version_click: Callable[..., None] | None = None,
    refresh_tooltip: str = "Refresh",
    fav_active: bool = False,
    show_search: bool = True,
    # Lifted from the parent (which rebuilds on state change): the chip
    # reads props, not the observable, so a state flip that rebuilds the
    # parent always repaints the chip. None = fall back to core_state.
    update_available: bool | None = None,
    update_label: str | None = None,
    update_announcement: bool = False,
) -> Control:
    page = _resolve_page()
    try:
        _theme_mode = page.theme_mode if page is not None else ft.ThemeMode.DARK
    except (RuntimeError, AttributeError):
        _theme_mode = ft.ThemeMode.DARK

    def _handle_toggle_theme():
        if page is None:
            return
        _toggle_theme_util(page)
        # No extra set_state: toggle_theme updates the page itself, which
        # schedules the repaint. Local state would double-render.

    def _build_version_chip() -> Control | None:
        """Sherlock-style version chip: shows the current version normally,
        flips to an Update pill when a newer build is found. Always opens
        the version dialog (changelog when up to date)."""
        if not callable(on_version_click):
            return None
        if update_available is None:
            has_update = core_state.update_available
            update_data = core_state.update_data
            is_announcement = getattr(update_data, "type", "") == "announcement"
            label = getattr(update_data, "version", None) or "Update"
        else:
            has_update = update_available
            is_announcement = update_announcement
            label = update_label or "Update"
        if has_update:
            content = ft.Row(
                controls=[
                    ft.Text(
                        "News" if is_announcement else f"Update: {label} Available!",
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
                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                border_radius=10,
                bgcolor=ft.Colors.with_opacity(0.15, AppColors.PRIMARY),
                border=ft.Border.all(1.5, AppColors.PRIMARY),
                ink=True,
                tooltip="New update available — tap to view",
                on_click=lambda e: _invoke(on_version_click, e),
            )
        return ft.Container(
            content=ft.Text(
                f"v{APP_VERSION}",
                size=11,
                weight=ft.FontWeight.BOLD,
                color=ft.Colors.ON_SURFACE_VARIANT,
                no_wrap=True,
            ),
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE_VARIANT),
            ink=True,
            tooltip="What's New — version & changelog",
            on_click=lambda e: _invoke(on_version_click, e),
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
        is_dark = AppColors.is_dark(page)
    except (RuntimeError, AttributeError):
        is_dark = True

    theme_icon = ft.Icons.DARK_MODE_ROUNDED if is_dark else ft.Icons.LIGHT_MODE_ROUNDED
    tooltip_text = (
        "Dark Mode (click for Light)" if is_dark else "Light Mode (click for Dark)"
    )
    actions.append(
        _make_icon_btn(
            icon=theme_icon,
            on_click=lambda e: _handle_toggle_theme(),
            tooltip=tooltip_text,
        )
    )

    # Brand mark: the SVG ships a blue (#00A2FF) line-art logo on
    # transparency. No color override — tinting it ON_SURFACE (blend
    # SRC_IN) would flatten the artwork to a silhouette. The file lives
    # in src/assets; a leading slash resolves against assets_dir ("src"
    # runs serve from src/, "assets" runs from the package root — Flet
    # tries both). error_content keeps the bar intact if it 404s.
    brand_mark = ft.Image(
        src="/icon.svg",
        width=38,
        height=38,
        error_content=ft.Icon(ft.Icons.LIVE_TV_ROUNDED, size=30),
        semantics_label="KTV Player",
    )

    return ft.Container(
        padding=ft.Padding.only(left=24, right=24, top=24, bottom=8),
        content=ft.Row(
            controls=[
                brand_mark,
                # Spacer absorbs narrow widths so the action cluster never
                # pushes the brand off-screen; the row scrolls as a last
                # resort on very small windows.
                ft.Container(expand=True),
                ft.Row(controls=actions, spacing=4, scroll=ft.ScrollMode.AUTO),
            ],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )
