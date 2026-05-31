"""Dashboard view — main screen with tabs, search, and recently watched."""

import asyncio
import logging

import flet as ft

from core.constants import (
    LBL_CATEGORIES,
    LBL_COUNTRIES,
    LBL_CUSTOM,
    LBL_LOADING_CHANNELS,
    LBL_LOADING_CHANNELS_SUB,
    LBL_LOCAL,
    LBL_RECENTLY_WATCHED,
    LBL_SEARCH_HINT,
    LBL_SETTINGS,
)
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from services.logo_cache import get_cached_logo
from views.tabs.channel_groups import build_channel_groups
from views.tabs.custom_tab import build_custom_tab_content
from views.tabs.local_tab import build_local_tab_content
from views.tabs.preferences_tab import build_preferences_tab_content

logger = logging.getLogger(__name__)


def build_dashboard_view(page_obj, on_play, ad_service, liveliness, load_channels):
    """Build the dashboard view. Returns ft.View."""
    view_state = {
        "selected_tab": 0,
        "search_query": "",
        "add_type": "playlist",
        "tab_built": [False, False, False, False, False],
    }

    tab_content = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=10)
    active_tiles = []

    # --- Tab Building with caching ---

    _tab_cache = [None, None, None, None, None]
    _loading_spinner = None

    def _get_loading_spinner():
        nonlocal _loading_spinner
        if _loading_spinner is None:
            _loading_spinner = ft.Column(
                [
                    ft.Container(height=80),
                    ft.ProgressRing(
                        width=60,
                        height=60,
                        stroke_width=6,
                        color=AppColors.PRIMARY,
                    ),
                    ft.Container(height=20),
                    ft.Text(
                        LBL_LOADING_CHANNELS,
                        color=AppColors.GREY_DIM,
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        LBL_LOADING_CHANNELS_SUB,
                        color=AppColors.GREY_DIM,
                        size=12,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        return _loading_spinner

    def build_tab(index):
        if state.is_loading:
            tab_content.controls.clear()
            tab_content.controls.append(_get_loading_spinner())
            page_obj.update()
            return

        has_query = bool(view_state["search_query"])

        # Use cache only for non-search, non-first-build
        if not has_query and _tab_cache[index] is not None:
            tab_content.controls.clear()
            active_tiles.clear()
            tab_content.controls.append(_tab_cache[index])
            page_obj.update()
            return

        tab_content.controls.clear()
        active_tiles.clear()

        inner = ft.Column(spacing=10, expand=True, scroll=ft.ScrollMode.AUTO)

        if index == 0:
            build_channel_groups(
                inner,
                1,
                page_obj,
                on_play,
                ad_service,
                liveliness,
                view_state,
                active_tiles,
            )
        elif index == 1:
            build_channel_groups(
                inner,
                0,
                page_obj,
                on_play,
                ad_service,
                liveliness,
                view_state,
                active_tiles,
            )
        elif index == 2:
            build_custom_tab_content(
                inner,
                page_obj,
                on_play,
                ad_service,
                liveliness,
                view_state,
                active_tiles,
            )
        elif index == 3:
            build_local_tab_content(
                inner,
                page_obj,
                on_play,
                ad_service,
                liveliness,
                view_state,
                active_tiles,
            )
        elif index == 4:
            build_preferences_tab_content(
                inner,
                page_obj,
                on_play,
                ad_service,
                liveliness,
                view_state,
                active_tiles,
            )

        view_state["tab_built"][index] = True

        # Only cache non-search builds
        if not has_query:
            _tab_cache[index] = inner

        tab_content.controls.append(inner)
        page_obj.update()

    def on_tab_change(e):
        index = e.control.selected_index
        view_state["selected_tab"] = index
        build_tab(index)

    def refresh_dashboard():
        # Invalidate caches on data change, but only rebuild current tab
        for i in range(len(_tab_cache)):
            _tab_cache[i] = None
        build_tab(view_state["selected_tab"])

    # --- Search with debounce ---

    _search_debounce_task: asyncio.Task | None = None

    def execute_search(e=None):
        nonlocal _search_debounce_task
        view_state["search_query"] = (
            search_field.value.strip() if search_field.value else ""
        )
        build_tab(view_state["selected_tab"])

    def on_search_change(e):
        nonlocal _search_debounce_task
        if _search_debounce_task is not None:
            _search_debounce_task.cancel()

        async def debounce():
            await asyncio.sleep(0.3)
            execute_search()

        _search_debounce_task = asyncio.create_task(debounce())

    search_field = ft.TextField(
        hint_text=LBL_SEARCH_HINT,
        border=ft.InputBorder.NONE,
        height=40,
        content_padding=ft.Padding(12, 0, 12, 0),
        on_change=on_search_change,
        on_submit=execute_search,
        expand=True,
    )

    # --- Recently Watched ---

    recently_watched_row = ft.Row(
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )
    _rw_tab_counter = 0

    def build_recently_watched():
        nonlocal _rw_tab_counter
        _rw_tab_counter = 0
        recently_watched_row.controls.clear()
        if not state.history:
            return

        channel_map = {c["url"]: c for c in state.channels if "url" in c}
        for url in state.history[:10]:
            ch = channel_map.get(url)
            if not ch:
                continue

            logo_src = ch.get("logo", "/icon.png")
            cached = (
                get_cached_logo(logo_src)
                if logo_src and not logo_src.startswith("/")
                else None
            )

            _rw_tab_counter += 1
            card = ft.Container(
                content=ft.Column(
                    [
                        ft.Image(
                            src=cached or logo_src,
                            width=50,
                            height=50,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=15,
                            error_content=ft.Icon(ft.Icons.TV, size=24),
                        ),
                        ft.Text(
                            ch.get("name", "Unknown"),
                            size=10,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            text_align=ft.TextAlign.CENTER,
                            width=70,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                padding=8,
                border_radius=12,
                ink=True,
                on_click=lambda e, u=url: page_obj.run_task(on_play, u),
            )
            card.tab_index = _rw_tab_counter
            recently_watched_row.controls.append(card)

    recently_watched_section = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Text(
                        LBL_RECENTLY_WATCHED,
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=AppColors.GREY_DIM,
                    ),
                    padding=ft.Padding(16, 8, 16, 4),
                ),
                ft.Container(
                    content=recently_watched_row,
                    padding=ft.Padding(16, 0, 16, 8),
                ),
            ],
            spacing=0,
        ),
        visible=bool(state.history),
    )

    # --- Theme Toggle ---

    def _resolve_effective_mode():
        if page_obj.theme_mode == ft.ThemeMode.SYSTEM:
            try:
                return (
                    ft.ThemeMode.DARK
                    if page_obj.platform_brightness == ft.Brightness.DARK
                    else ft.ThemeMode.LIGHT
                )
            except Exception:
                return ft.ThemeMode.DARK
        return page_obj.theme_mode

    def handle_theme_toggle(e):
        current = _resolve_effective_mode()
        new_mode = (
            ft.ThemeMode.LIGHT if current == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        )
        page_obj.theme_mode = new_mode
        theme_btn.content = ft.Icon(
            ft.Icons.LIGHT_MODE
            if new_mode == ft.ThemeMode.DARK
            else ft.Icons.DARK_MODE,
            color=ft.Colors.ON_SURFACE,
        )
        theme_btn.update()
        page_obj.run_task(
            db_manager.set_setting,
            "theme_mode",
            "dark" if new_mode == ft.ThemeMode.DARK else "light",
        )
        page_obj.update()

    initial_mode = _resolve_effective_mode()
    theme_btn = ft.Container(
        content=ft.Icon(
            ft.Icons.LIGHT_MODE
            if initial_mode == ft.ThemeMode.DARK
            else ft.Icons.DARK_MODE,
            color=ft.Colors.ON_SURFACE,
        ),
        padding=10,
        border_radius=10,
        ink=True,
        on_click=handle_theme_toggle,
    )
    theme_btn.tab_index = 0

    # --- Header ---

    header = ft.Container(
        padding=ft.Padding(12, 12, 12, 8),
        content=ft.Row(
            [
                ft.Image(src="icon.png", width=36, height=36, fit=ft.BoxFit.CONTAIN),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.SEARCH, color=AppColors.GREY_DIM, size=18),
                            search_field,
                        ],
                        spacing=6,
                    ),
                    padding=ft.Padding(10, 0, 4, 0),
                    border=ft.Border.all(1, AppColors.GREY_DIM),
                    border_radius=10,
                    expand=True,
                ),
                theme_btn,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    # --- Tabs ---

    tab_bar = ft.TabBar(
        tabs=[
            ft.Tab(label=LBL_CATEGORIES, icon=ft.Icons.CATEGORY),
            ft.Tab(label=LBL_COUNTRIES, icon=ft.Icons.PUBLIC),
            ft.Tab(label=LBL_CUSTOM, icon=ft.Icons.PLAYLIST_ADD),
            ft.Tab(label=LBL_LOCAL, icon=ft.Icons.FOLDER),
            ft.Tab(label=LBL_SETTINGS, icon=ft.Icons.SETTINGS),
        ],
    )

    tabs_wrapper = ft.Tabs(
        length=5,
        selected_index=0,
        content=ft.Column([tab_bar, tab_content], expand=True, spacing=0),
        expand=True,
        on_change=on_tab_change,
    )

    # --- Assemble View ---

    ad_banner = ad_service.get_anchor_banner_ad()
    footer_controls = (
        [
            ft.Container(
                content=ad_banner,
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding(0, 5, 0, 5),
            ),
        ]
        if ad_banner
        else []
    )

    view = ft.View(
        route="/dashboard",
        controls=[
            ft.SafeArea(
                ft.Column(
                    [
                        header,
                        recently_watched_section,
                        ft.Container(
                            content=tabs_wrapper,
                            expand=True,
                            padding=ft.Padding(8, 0, 8, 0),
                        ),
                    ],
                    expand=True,
                    spacing=0,
                ),
                expand=True,
            ),
            *footer_controls,
        ],
        padding=0,
    )

    # Store callbacks so child tabs can use them
    page_obj._dashboard_refresh = refresh_dashboard
    page_obj.load_channels = load_channels

    # Build initial tab and recently watched
    build_recently_watched()
    build_tab(0)

    return view
