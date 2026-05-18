import asyncio
import logging

import flet as ft

from core.constants import (
    LBL_CATEGORIES,
    LBL_COUNTRIES,
    LBL_CUSTOM,
    LBL_LOADING_CHANNELS,
    LBL_LOADING_CHANNELS_SUB,
    LBL_LOCAL_VIDEOS,
    LBL_RECENTLY_WATCHED,
    LBL_SEARCH_HINT,
    LBL_SETTINGS,
    SEARCH_DEBOUNCE,
)
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from services.ad_service import AdService
from views.tabs.categories_tab import build_categories_tab_content
from views.tabs.countries_tab import build_countries_tab_content
from views.tabs.custom_tab import build_custom_tab_content
from views.tabs.local_tab import build_local_tab_content
from views.tabs.preferences_tab import build_preferences_tab_content

logger = logging.getLogger(__name__)


async def _toggle_theme(page_obj: ft.Page):
    from core.theme import AppColors
    AppColors.invalidate_brightness_cache()
    new_mode = ft.ThemeMode.LIGHT if page_obj.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
    page_obj.theme_mode = new_mode
    state.theme_mode = new_mode
    await db_manager.set_setting("theme_mode", "light" if new_mode == ft.ThemeMode.LIGHT else "dark")
    page_obj.update()


def build_dashboard_view(page_obj: ft.Page, on_play: callable, ad_service: AdService) -> ft.View:
    view_state = {
        "selected_tab": 0,
        "search_query": "",
        "add_type": "playlist",
        "search_task": None,
        "tab_built": [False, False, False, False, False],
        "recent_urls": [],
    }

    _active_tiles = []

    recently_watched_row = ft.Row(
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
        visible=False,
    )

    async def _load_recently_watched():
        history = await db_manager.get_history()
        if not history:
            return

        url_to_channel = {c.get("url"): c for c in state.channels}
        view_state["recent_urls"] = history[:8]
        recently_watched_row.controls.clear()

        for url in history[:8]:
            channel_info = url_to_channel.get(url)
            if not channel_info:
                continue
            name = channel_info.get("name", "")
            if not name:
                continue
            logo = channel_info.get("logo", "/icon.png")

            card = ft.Container(
                content=ft.Column(
                    [
                        ft.Image(
                            src=logo,
                            width=50,
                            height=50,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=12,
                            error_content=ft.Icon(ft.Icons.TV, size=30),
                        ),
                        ft.Text(
                            name,
                            size=10,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                width=80,
                padding=8,
                border_radius=12,
                ink=True,
                on_click=lambda e, play_url=url: page_obj.run_task(on_play, play_url),
            )
            recently_watched_row.controls.append(card)

        if recently_watched_row.controls:
            recently_watched_row.visible = True
            recently_watched_section.visible = True
        page_obj.update()

    recently_watched_section = ft.Column(
        [
            ft.Text(LBL_RECENTLY_WATCHED, size=14, weight=ft.FontWeight.W_600),
            recently_watched_row,
        ],
        visible=False,
    )

    page_obj.run_task(_load_recently_watched)

    categories_content = ft.ListView(expand=True, spacing=15)
    countries_content = ft.ListView(expand=True, spacing=15)
    custom_content = ft.ListView(expand=True, spacing=15)
    local_content = ft.ListView(expand=True, spacing=15)
    preferences_content = ft.ListView(expand=True, spacing=15)

    all_targets = [categories_content, countries_content, custom_content, local_content, preferences_content]

    liveliness = getattr(page_obj, "get_liveliness", lambda: None)()
    if liveliness is None:
        from services.liveliness_checker import LivelinessChecker
        liveliness = LivelinessChecker(page_obj)

    def update_tab_content(tab_index: int, force: bool = False):
        if not force and view_state["tab_built"][tab_index]:
            return

        target = all_targets[tab_index]
        target.controls.clear()

        if state.is_loading:
            target.controls.append(
                ft.Column(
                    [
                        ft.Container(height=80),
                        ft.ProgressRing(width=60, height=60, stroke_width=6, color=AppColors.PRIMARY),
                        ft.Container(height=20),
                        ft.Text(LBL_LOADING_CHANNELS, color=AppColors.GREY_DIM, size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(LBL_LOADING_CHANNELS_SUB, color=AppColors.GREY_DIM, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
            return

        target._refresh_tab = lambda ti: update_tab_content(ti)

        if tab_index == 0:
            build_categories_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, _active_tiles)
        elif tab_index == 1:
            build_countries_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, _active_tiles)
        elif tab_index == 2:
            build_custom_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, _active_tiles)
        elif tab_index == 3:
            build_local_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, _active_tiles)
        elif tab_index == 4:
            build_preferences_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, _active_tiles)

        view_state["tab_built"][tab_index] = True

    tab_view_container = ft.TabBarView(
        controls=all_targets,
        expand=True,
    )

    def handle_tab_change(e):
        view_state["selected_tab"] = int(e.data)
        update_tab_content(view_state["selected_tab"])
        page_obj.update()

    tab_bar = ft.TabBar(
        tabs=[
            ft.Tab(label=LBL_CATEGORIES, icon=ft.Icons.CATEGORY),
            ft.Tab(label=LBL_COUNTRIES, icon=ft.Icons.PUBLIC),
            ft.Tab(label=LBL_CUSTOM, icon=ft.Icons.PLAYLIST_ADD),
            ft.Tab(label=LBL_LOCAL_VIDEOS, icon=ft.Icons.VIDEO_LIBRARY),
            ft.Tab(label=LBL_SETTINGS, icon=ft.Icons.SETTINGS),
        ]
    )

    tabs_wrapper = ft.Tabs(
        length=5,
        selected_index=view_state["selected_tab"],
        content=ft.Column([tab_bar, tab_view_container], expand=True, spacing=0),
        expand=True,
        on_change=handle_tab_change,
    )

    def refresh_dashboard(tab_index: int | None = None):
        if tab_index is not None:
            view_state["tab_built"][tab_index] = False
            update_tab_content(tab_index, force=True)
        else:
            for i in range(5):
                view_state["tab_built"][i] = False
            update_tab_content(view_state["selected_tab"], force=True)
        page_obj.run_task(_load_recently_watched)
        page_obj.update()

    page_obj.refresh_dashboard = refresh_dashboard

    async def execute_search(query: str):
        view_state["search_query"] = query
        for i in range(5):
            view_state["tab_built"][i] = False
        update_tab_content(view_state["selected_tab"], force=True)
        page_obj.update()

    def on_search_change(e):
        if view_state["search_task"] and not view_state["search_task"].done():
            view_state["search_task"].cancel()

        query = e.data

        async def delayed_search():
            await asyncio.sleep(SEARCH_DEBOUNCE)
            await execute_search(query)

        view_state["search_task"] = page_obj.run_task(delayed_search)

    search_field = ft.TextField(
        on_change=on_search_change,
        hint_text=LBL_SEARCH_HINT,
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        expand=True,
        border=ft.InputBorder.OUTLINE,
        border_radius=12,
    )

    update_tab_content(0)

    header = ft.Row(
        [
            ft.Container(
                content=ft.Image(src="/icon.png", width=40, height=40, border_radius=12),
                border_radius=12,
            ),
            search_field,
            ft.Container(
                content=ft.IconButton(
                    icon=ft.Icons.LIGHT_MODE if page_obj.theme_mode == ft.ThemeMode.DARK else ft.Icons.DARK_MODE,
                    on_click=lambda _: page_obj.run_task(_toggle_theme, page_obj),
                ),
                border_radius=12,
                ink=True,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        spacing=20,
    )

    main_col = ft.Column(
        [header, recently_watched_section, tabs_wrapper],
        spacing=15,
        expand=True,
    )

    ad_banner = ad_service.get_anchor_banner_ad()
    footer_controls = [
        ft.Container(
            content=ad_banner,
            alignment=ft.Alignment.CENTER,
            padding=ft.Padding(0, 5, 0, 5),
        )
    ] if ad_banner else []

    return ft.View(
        route="/dashboard",
        controls=[
            ft.SafeArea(
                ft.Container(
                    content=main_col,
                    expand=True,
                    padding=20,
                    bgcolor=ft.Colors.SURFACE,
                ),
                expand=True,
            ),
            *footer_controls,
        ],
        padding=0,
    )
