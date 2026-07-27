"""Dashboard view — main screen with tabs, search, and recently watched."""

import logging

import flet as ft

from core.constants import (
    LBL_CATEGORIES,
    LBL_COUNTRIES,
    LBL_CUSTOM,
    LBL_LOADING_CHANNELS,
    LBL_LOADING_CHANNELS_SUB,
    LBL_LOCAL,
    LBL_SEARCH_HINT,
    LBL_SETTINGS,
)
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from views.dashboard_carousel import build_recently_watched_section
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
    _tab_cache = [None, None, None, None, None]
    _loading_spinner = None

    def _get_loading_spinner():
        nonlocal _loading_spinner
        if _loading_spinner is None:
            _loading_spinner = ft.Column(
                [
                    ft.Container(height=80),
                    ft.ProgressRing(
                        width=60, height=60, stroke_width=6, color=AppColors.PRIMARY
                    ),
                    ft.Container(height=20),
                    ft.Text(
                        LBL_LOADING_CHANNELS,
                        color=AppColors.GREY_DIM,
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        LBL_LOADING_CHANNELS_SUB, color=AppColors.GREY_DIM, size=12
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
        if not has_query:
            _tab_cache[index] = inner

        tab_content.controls.append(inner)
        page_obj.update()

    def on_tab_change(e):
        index = e.control.selected_index
        view_state["selected_tab"] = index
        build_tab(index)

    def refresh_dashboard():
        for i in range(len(_tab_cache)):
            _tab_cache[i] = None
        refresh_carousel()
        recently_watched_section.visible = bool(state.history)
        build_tab(view_state["selected_tab"])

    page_obj._dashboard_refresh = refresh_dashboard

    def execute_search(e=None):
        view_state["search_query"] = (
            search_field.value.strip() if search_field.value else ""
        )
        build_tab(view_state["selected_tab"])

    search_field = ft.SearchBar(
        bar_hint_text=LBL_SEARCH_HINT,
        bar_leading=ft.Icon(ft.Icons.SEARCH_ROUNDED, color=ft.Colors.PRIMARY),
        bar_elevation=0,
        bar_padding=ft.Padding(12, 0, 12, 0),
        on_change=execute_search,
        on_submit=execute_search,
        expand=True,
    )

    recently_watched_section, refresh_carousel = build_recently_watched_section(
        page_obj, on_play
    )

    def _resolve_effective_mode():
        if page_obj.theme_mode == ft.ThemeMode.SYSTEM:
            try:
                return page_obj.platform_brightness == ft.Brightness.DARK
            except Exception:
                return True
        return page_obj.theme_mode == ft.ThemeMode.DARK

    def toggle_theme(e):
        is_dark = _resolve_effective_mode()
        new_mode = ft.ThemeMode.LIGHT if is_dark else ft.ThemeMode.DARK
        page_obj.theme_mode = new_mode

        async def _save():
            await db_manager.set_setting(
                "theme_mode", "dark" if new_mode == ft.ThemeMode.DARK else "light"
            )

        page_obj.run_task(_save)
        theme_btn.icon = (
            ft.Icons.LIGHT_MODE if new_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE
        )
        refresh_dashboard()

    init_is_dark = _resolve_effective_mode()
    theme_btn = ft.IconButton(
        icon=ft.Icons.LIGHT_MODE if init_is_dark else ft.Icons.DARK_MODE,
        tooltip="Toggle Theme",
        on_click=toggle_theme,
        icon_size=18,
    )

    header = ft.Row(
        [
            ft.Row(
                [
                    ft.Image(
                        src="/icon.png",
                        width=36,
                        height=36,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=8,
                    ),
                    ft.Text("KTV Player", size=18, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            search_field,
            theme_btn,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    tabs = ft.Tabs(
        length=5,  # Number of tabs
        selected_index=0,
        on_change=on_tab_change,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(
                    tabs=[
                        ft.Tab(label=LBL_CATEGORIES, icon=ft.Icons.GRID_VIEW_ROUNDED),
                        ft.Tab(label=LBL_COUNTRIES, icon=ft.Icons.PUBLIC_ROUNDED),
                        ft.Tab(label=LBL_CUSTOM, icon=ft.Icons.PLAYLIST_ADD_ROUNDED),
                        ft.Tab(label=LBL_LOCAL, icon=ft.Icons.FOLDER_ROUNDED),
                        ft.Tab(label=LBL_SETTINGS, icon=ft.Icons.SETTINGS_ROUNDED),
                    ]
                ),
                ft.TabBarView(
                    expand=True,
                    controls=[tab_content],
                ),
            ],
        ),
    )

    body = ft.Column(
        [
            recently_watched_section,
            ft.Container(
                content=tab_content, expand=True, padding=ft.Padding(12, 0, 12, 12)
            ),
        ],
        expand=True,
        spacing=0,
    )

    if ad_service:
        banner = ad_service.get_anchor_banner_ad()
        if banner:
            body.controls.append(banner)

    build_tab(0)

    return ft.View(
        route="/dashboard",
        controls=[
            ft.Container(
                content=ft.Column(
                    [
                        ft.Container(content=header, padding=ft.Padding(12, 8, 12, 4)),
                        tabs,
                        body,
                    ],
                    expand=True,
                    spacing=0,
                ),
                expand=True,
            ),
        ],
        padding=0,
    )
