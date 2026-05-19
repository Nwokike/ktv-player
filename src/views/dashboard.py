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
    LBL_RECENTLY_WATCHED,
    LBL_SEARCH_HINT,
    LBL_SETTINGS,
)
from core.focus_manager import make_focusable_button
from core.state import state
from core.theme import AppColors
from services.logo_cache import get_cached_logo

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

    # --- Tab Building ---

    def build_tab(index):
        from views.tabs.channel_groups import build_channel_groups
        from views.tabs.custom_tab import build_custom_tab_content
        from views.tabs.local_tab import build_local_tab_content
        from views.tabs.preferences_tab import build_preferences_tab_content

        tab_content.controls.clear()
        active_tiles.clear()

        if state.is_loading:
            tab_content.controls.append(
                ft.Column(
                    [
                        ft.Container(height=80),
                        ft.ProgressRing(width=60, height=60, stroke_width=6, color=AppColors.PRIMARY),
                        ft.Container(height=20),
                        ft.Text(LBL_LOADING_CHANNELS, color=AppColors.GREY_DIM, size=16, weight=ft.FontWeight.BOLD),
                        ft.Text(LBL_LOADING_CHANNELS_SUB, color=AppColors.GREY_DIM, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
            page_obj.update()
            return

        if index == 0:  # Countries
            build_channel_groups(tab_content, 0, page_obj, on_play, ad_service, liveliness, view_state, active_tiles)
        elif index == 1:  # Categories
            build_channel_groups(tab_content, 1, page_obj, on_play, ad_service, liveliness, view_state, active_tiles)
        elif index == 2:  # Custom
            build_custom_tab_content(tab_content, page_obj, on_play, ad_service, liveliness, view_state, active_tiles)
        elif index == 3:  # Local
            build_local_tab_content(tab_content, page_obj, on_play, ad_service, liveliness, view_state, active_tiles)
        elif index == 4:  # Settings
            build_preferences_tab_content(tab_content, page_obj, on_play, ad_service, liveliness, view_state, active_tiles)

        view_state["tab_built"][index] = True
        page_obj.update()

    def on_tab_change(e):
        index = e.control.selected_index
        view_state["selected_tab"] = index
        view_state["search_query"] = ""
        search_field.value = ""
        build_tab(index)

    def refresh_dashboard():
        build_tab(view_state["selected_tab"])

    # --- Search ---

    def execute_search(e=None):
        view_state["search_query"] = search_field.value.strip() if search_field.value else ""
        build_tab(view_state["selected_tab"])

    search_field = ft.TextField(
        hint_text=LBL_SEARCH_HINT,
        border=ft.InputBorder.NONE,
        height=40,
        content_padding=ft.Padding(12, 0, 12, 0),
        on_submit=execute_search,
        expand=True,
    )


    # --- Recently Watched ---

    recently_watched_row = ft.Row(
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )

    def build_recently_watched():
        recently_watched_row.controls.clear()
        if not state.history:
            return

        channel_map = {c["url"]: c for c in state.channels if "url" in c}
        for url in state.history[:10]:
            ch = channel_map.get(url)
            if not ch:
                continue

            logo_src = ch.get("logo", "/icon.png")
            cached = get_cached_logo(logo_src) if logo_src and not logo_src.startswith("/") else None

            card = ft.Container(
                content=ft.Column(
                    [
                        ft.Image(
                            src=cached or logo_src,
                            width=50, height=50, fit=ft.BoxFit.CONTAIN, border_radius=15,
                            error_content=ft.Icon(ft.Icons.TV, size=24),
                        ),
                        ft.Text(
                            ch.get("name", "Unknown"), size=10,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                            text_align=ft.TextAlign.CENTER, width=70,
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
            card.tab_index = 0
            make_focusable_button(card)
            recently_watched_row.controls.append(card)

    recently_watched_section = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Text(LBL_RECENTLY_WATCHED, size=14, weight=ft.FontWeight.W_600, color=AppColors.GREY_DIM),
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

    def handle_theme_toggle(e):
        page_obj.theme_mode = ft.ThemeMode.LIGHT if page_obj.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        theme_btn.content = ft.Icon(
            ft.Icons.LIGHT_MODE if page_obj.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE,
            color=ft.Colors.ON_SURFACE,
        )
        page_obj.update()

    theme_btn = ft.Container(
        content=ft.Icon(
            ft.Icons.LIGHT_MODE if page_obj.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE,
            color=ft.Colors.ON_SURFACE,
        ),
        padding=10,
        border_radius=10,
        ink=True,
        on_click=handle_theme_toggle,
    )
    theme_btn.tab_index = 0
    make_focusable_button(theme_btn)

    # --- Header (icon + search + theme toggle on one line) ---

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
            ft.Tab(label=LBL_COUNTRIES, icon=ft.Icons.PUBLIC),
            ft.Tab(label=LBL_CATEGORIES, icon=ft.Icons.CATEGORY),
            ft.Tab(label=LBL_CUSTOM, icon=ft.Icons.PLAYLIST_ADD),
            ft.Tab(label=LBL_LOCAL, icon=ft.Icons.FOLDER),
            ft.Tab(label=LBL_SETTINGS, icon=ft.Icons.SETTINGS),
        ]
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
    footer_controls = [
        ft.Container(
            content=ad_banner,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding(0, 5, 0, 5),
        )
    ] if ad_banner else []

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

    # Attach callbacks for child tabs to use
    page_obj.refresh_dashboard = refresh_dashboard
    page_obj.load_channels = load_channels

    # Build initial tab and recently watched
    build_recently_watched()
    build_tab(0)

    return view

