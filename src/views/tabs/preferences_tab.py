import contextlib

import flet as ft

from core.constants import (
    LBL_CLEAR_HISTORY,
    LBL_CLEAR_HISTORY_DESC,
    LBL_DATA_MANAGEMENT,
    LBL_HISTORY_CLEARED,
    LBL_LIBRARY_RESET,
    LBL_LOCALIZATION,
    LBL_LOCALIZATION_DESC,
    LBL_PREFERENCES,
    LBL_RESET_LIBRARY,
    LBL_RESET_LIBRARY_DESC,
)
from core.state import state
from core.theme import AppColors
from database.manager import db_manager


def build_preferences_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, active_tiles):
    async def handle_clear_history(e):
        await db_manager.clear_history()
        page_obj.snack_bar = ft.SnackBar(
            ft.Text(LBL_HISTORY_CLEARED), bgcolor=AppColors.SUCCESS
        )
        page_obj.snack_bar.open = True
        page_obj.update()

    async def handle_clear_custom(e):
        state.is_loading = True
        refresh_tab = getattr(target, "_refresh_tab", None)
        if refresh_tab:
            refresh_tab(view_state["selected_tab"])
        page_obj.update()

        await db_manager.clear_custom_content()
        if hasattr(page_obj, "load_channels"):
            await page_obj.load_channels()

        state.is_loading = False
        if refresh_tab:
            refresh_tab(view_state["selected_tab"])

        page_obj.snack_bar = ft.SnackBar(
            ft.Text(LBL_LIBRARY_RESET), bgcolor=AppColors.SUCCESS
        )
        page_obj.snack_bar.open = True
        page_obj.update()

    unique_countries = sorted(
        list(
            set(
                [
                    c.get("group", "").split(";")[0].strip()
                    for c in state.channels
                    if c.get("country_code")
                ]
            )
        )
    )
    if "Other" not in unique_countries:
        unique_countries.append("Other")
    if not unique_countries or (
        len(unique_countries) == 1 and unique_countries[0] == "Other"
    ):
        unique_countries = ["Global", "Nigeria", "USA", "UK", "Other"]

    settings_country_list = ft.ListView(height=180, spacing=2, padding=5, auto_scroll=False)
    settings_country_tiles = []

    def _settings_select_country(name):
        async def _do_select():
            await db_manager.set_setting("user_country", name)
            state.user_country = name
            for ti in settings_country_tiles:
                is_sel = ti["name"] == name
                ti["tile"].bgcolor = AppColors.PRIMARY if is_sel else None
                ti["tile"].leading = ft.Icon(
                    ft.Icons.CHECK_CIRCLE if is_sel else ft.Icons.RADIO_BUTTON_UNCHECKED,
                    color=ft.Colors.WHITE if is_sel else AppColors.GREY_DIM,
                )
                ti["tile"].title = ft.Text(
                    ti["name"],
                    color=ft.Colors.WHITE if is_sel else None,
                    weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.NORMAL,
                )
            settings_country_list.update()
            page_obj.snack_bar = ft.SnackBar(
                ft.Text(f"Primary country updated to {name}")
            )
            page_obj.snack_bar.open = True
            page_obj.update()
        page_obj.run_task(_do_select)

    for cname in unique_countries:
        is_current = cname == state.user_country
        stile = ft.ListTile(
            title=ft.Text(
                cname,
                color=ft.Colors.WHITE if is_current else None,
                weight=ft.FontWeight.W_600 if is_current else ft.FontWeight.NORMAL,
            ),
            leading=ft.Icon(
                ft.Icons.CHECK_CIRCLE if is_current else ft.Icons.RADIO_BUTTON_UNCHECKED,
                color=ft.Colors.WHITE if is_current else AppColors.GREY_DIM,
            ),
            key=cname,
            bgcolor=AppColors.PRIMARY if is_current else None,
            on_click=lambda e, n=cname: _settings_select_country(n),
            dense=True,
            shape=ft.RoundedRectangleBorder(radius=8),
        )
        stile.on_focus = lambda e, sl=settings_country_list: _tile_focus_scroll(e, sl)

        settings_country_tiles.append({"name": cname, "tile": stile})
        settings_country_list.controls.append(stile)

    country_picker = ft.Container(
        content=settings_country_list,
        border=ft.Border.all(1, AppColors.GREY_DIM),
        border_radius=10,
    )

    target.controls.append(
        ft.Column(
            [
                ft.Text(LBL_PREFERENCES, size=24, weight=ft.FontWeight.BOLD),
                ft.Divider(height=20),
                ft.Text(
                    LBL_LOCALIZATION,
                    size=16,
                    weight=ft.FontWeight.W_600,
                    color=AppColors.PRIMARY,
                ),
                ft.Text(
                    LBL_LOCALIZATION_DESC,
                    size=12,
                    color=AppColors.GREY_DIM,
                ),
                country_picker,
                ft.Container(height=20),
                ft.Text(
                    LBL_DATA_MANAGEMENT,
                    size=16,
                    weight=ft.FontWeight.W_600,
                    color=AppColors.PRIMARY,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.HISTORY, color=AppColors.WARNING),
                    title=ft.Text(LBL_CLEAR_HISTORY),
                    subtitle=ft.Text(LBL_CLEAR_HISTORY_DESC),
                    on_click=handle_clear_history,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.DELETE_FOREVER, color=AppColors.WARNING),
                    title=ft.Text(LBL_RESET_LIBRARY),
                    subtitle=ft.Text(LBL_RESET_LIBRARY_DESC),
                    on_click=handle_clear_custom,
                ),
            ],
            spacing=10,
            expand=True,
        )
    )


def _tile_focus_scroll(e, scrollable):
    ck = getattr(e.control, "key", None)
    if ck and hasattr(scrollable, "scroll_to"):
        with contextlib.suppress(Exception):
            scrollable.scroll_to(key=ck, duration=200)
