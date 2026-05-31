"""Onboarding view — first-launch country selection and terms acceptance."""

import asyncio
import contextlib

import flet as ft

from core.constants import (
    LBL_PLEASE_ACCEPT_TERMS,
    LBL_PLEASE_SELECT_COUNTRY,
    LBL_SELECT_COUNTRY,
    LBL_START_WATCHING,
    LBL_TV_NAV_HINT,
    LBL_USAGE_AGREEMENT,
    LBL_WELCOME,
    LBL_WELCOME_SUB,
    TERMS_TEXT,
)
from core.state import state
from core.theme import AppColors
from database.manager import db_manager


def build_onboarding_view(
    page_obj: ft.Page,
    countries: list[dict],
    on_complete: callable,
    load_channels: callable = None,
) -> ft.View:
    selected_state = {"country": ""}
    content_container = ft.Container(expand=True)

    retry_btn = ft.Ref[ft.FilledButton]()
    offline_btn = ft.Ref[ft.OutlinedButton]()

    async def handle_retry(e):
        if not load_channels:
            return

        # Show loading indicator on button
        retry_btn.current.disabled = True
        retry_btn.current.icon = None
        retry_btn.current.content = "Connecting..."
        page_obj.update()

        try:
            await load_channels(force=True)
            if state.channels:
                from channels.provider import channel_provider

                fresh_countries = channel_provider.get_countries()
                render_content(fresh_countries)
            else:
                page_obj.snack_bar = ft.SnackBar(
                    ft.Text(
                        "Still unable to connect. Please check your network and try again.",
                    ),
                    bgcolor=AppColors.ERROR,
                )
                page_obj.snack_bar.open = True
        except Exception as err:
            page_obj.snack_bar = ft.SnackBar(
                ft.Text(f"Connection failed: {str(err)}"),
                bgcolor=AppColors.ERROR,
            )
            page_obj.snack_bar.open = True
        finally:
            retry_btn.current.disabled = False
            retry_btn.current.icon = ft.Icons.REFRESH
            retry_btn.current.content = "Retry Connection"
            page_obj.update()

    async def handle_offline_mode(e):
        # Set default user country and accept terms
        await db_manager.set_setting("user_country", "Other")
        await db_manager.set_setting("has_accepted_terms", "true")
        state.user_country = "Other"
        state.has_accepted_terms = True
        state.is_first_launch = False

        if asyncio.iscoroutinefunction(on_complete):
            await on_complete()
        else:
            on_complete()

    def render_content(current_countries: list[dict]):
        if not state.channels:
            # Render Offline UI
            offline_retry_btn = ft.FilledButton(
                ref=retry_btn,
                content="Retry Connection",
                icon=ft.Icons.REFRESH,
                on_click=handle_retry,
                style=ft.ButtonStyle(
                    color="white",
                    bgcolor=AppColors.PRIMARY,
                    padding=ft.Padding(32, 16, 32, 16),
                    shape=ft.RoundedRectangleBorder(radius=16),
                ),
                width=320,
            )

            offline_mode_btn = ft.OutlinedButton(
                ref=offline_btn,
                content="Continue to Offline Mode",
                icon=ft.Icons.PLAY_ARROW_ROUNDED,
                on_click=handle_offline_mode,
                style=ft.ButtonStyle(
                    color=AppColors.PRIMARY,
                    padding=ft.Padding(32, 16, 32, 16),
                    shape=ft.RoundedRectangleBorder(radius=16),
                    side=ft.BorderSide(2, AppColors.PRIMARY),
                ),
                width=320,
            )

            offline_card = ft.Container(
                content=ft.Column(
                    [
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.WIFI_OFF_ROUNDED,
                                size=48,
                                color=AppColors.PRIMARY,
                            ),
                            bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
                            padding=20,
                            border_radius=50,
                        ),
                        ft.Container(height=10),
                        ft.Text(
                            "Connection Required",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            "KTV Player needs an active internet connection to download the initial TV playlist and complete setup. "
                            "Please check your Wi-Fi or mobile data.",
                            size=14,
                            text_align=ft.TextAlign.CENTER,
                            color=AppColors.GREY_DIM,
                            width=340,
                        ),
                        ft.Container(height=15),
                        offline_retry_btn,
                        ft.Container(height=5),
                        offline_mode_btn,
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=10,
                ),
                padding=30,
                border_radius=20,
                bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
                border=ft.Border.all(
                    1,
                    ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                ),
                alignment=ft.Alignment(0, 0),
            )

            content_container.content = ft.Column(
                [
                    ft.Container(height=40),
                    ft.Column(
                        [
                            ft.Image(
                                src="/icon.png",
                                width=90,
                                height=90,
                                border_radius=20,
                            ),
                            ft.Text(
                                LBL_WELCOME,
                                size=34,
                                weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(height=20),
                    offline_card,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                scroll=ft.ScrollMode.AUTO,
                expand=True,
            )
            return

        # Online Flow
        terms_checked = ft.Ref[ft.Checkbox]()
        country_list = ft.ListView(height=220, spacing=3, padding=6, auto_scroll=False)
        all_country_tiles = []

        def select_country(name: str):
            selected_state["country"] = name
            for entry in all_country_tiles:
                is_sel = entry["name"] == name
                entry["tile"].bgcolor = AppColors.PRIMARY if is_sel else None
                entry["tile"].leading = ft.Icon(
                    ft.Icons.CHECK_CIRCLE
                    if is_sel
                    else ft.Icons.RADIO_BUTTON_UNCHECKED,
                    color=ft.Colors.WHITE if is_sel else AppColors.GREY_DIM,
                )
                entry["tile"].title = ft.Text(
                    entry["name"],
                    color=ft.Colors.WHITE if is_sel else None,
                    weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.NORMAL,
                )
            country_list.update()

        countries_list_copy = list(current_countries)
        if not countries_list_copy:
            countries_list_copy = [{"name": "Global"}]
        country_names = [c["name"] for c in countries_list_copy]
        if "Other" not in country_names:
            countries_list_copy.append({"name": "Other"})

        for c in countries_list_copy:
            cname = c["name"]
            tile = ft.ListTile(
                title=ft.Text(cname, size=14),
                leading=ft.Icon(
                    ft.Icons.RADIO_BUTTON_UNCHECKED,
                    color=AppColors.GREY_DIM,
                ),
                key=cname,
                on_click=lambda e, name=cname: select_country(name),
                dense=True,
                shape=ft.RoundedRectangleBorder(radius=12),
            )
            tile.on_focus = lambda e: _scroll_to_focused(e, country_list)
            all_country_tiles.append({"name": cname, "tile": tile})
            country_list.controls.append(tile)

        async def handle_submit(e):
            if not terms_checked.current.value:
                page_obj.snack_bar = ft.SnackBar(
                    ft.Text(LBL_PLEASE_ACCEPT_TERMS),
                    bgcolor=AppColors.WARNING,
                )
                page_obj.snack_bar.open = True
                page_obj.update()
                return

            if not selected_state["country"]:
                page_obj.snack_bar = ft.SnackBar(
                    ft.Text(LBL_PLEASE_SELECT_COUNTRY),
                    bgcolor=AppColors.WARNING,
                )
                page_obj.snack_bar.open = True
                page_obj.update()
                return

            country_name = selected_state["country"]
            await db_manager.set_setting("user_country", country_name)
            await db_manager.set_setting("has_accepted_terms", "true")
            state.user_country = country_name
            state.has_accepted_terms = True
            state.is_first_launch = False

            if asyncio.iscoroutinefunction(on_complete):
                await on_complete()
            else:
                on_complete()

        content = ft.ListView(
            controls=[
                ft.Container(height=30),
                ft.Column(
                    [
                        ft.Image(
                            src="/icon.png",
                            width=90,
                            height=90,
                            border_radius=20,
                        ),
                        ft.Text(
                            LBL_WELCOME,
                            size=34,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            LBL_WELCOME_SUB,
                            size=15,
                            text_align=ft.TextAlign.CENTER,
                            color=AppColors.GREY_DIM,
                            width=400,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                ft.Divider(height=24, color=ft.Colors.TRANSPARENT),
                ft.Text(
                    LBL_SELECT_COUNTRY,
                    size=18,
                    weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER,
                    width=float("inf"),
                ),
                ft.Text(
                    LBL_TV_NAV_HINT,
                    size=12,
                    color=AppColors.GREY_DIM,
                    text_align=ft.TextAlign.CENTER,
                    width=float("inf"),
                ),
                ft.Container(
                    content=country_list,
                    border=ft.Border.all(1.5, AppColors.GREY_DIM),
                    border_radius=14,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                    padding=4,
                ),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.Container(
                    content=ft.Text(
                        TERMS_TEXT,
                        size=12,
                        color=AppColors.GREY_DIM,
                        text_align=ft.TextAlign.LEFT,
                    ),
                    padding=16,
                    border_radius=12,
                    border=ft.Border.all(1, AppColors.GREY_DIM),
                ),
                ft.Row(
                    [
                        ft.Checkbox(ref=terms_checked, value=False),
                        ft.Text(
                            LBL_USAGE_AGREEMENT,
                            size=14,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                    wrap=True,
                ),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.FilledButton(
                    content=LBL_START_WATCHING,
                    on_click=handle_submit,
                    style=ft.ButtonStyle(
                        color="white",
                        bgcolor=AppColors.PRIMARY,
                        padding=ft.Padding(32, 16, 32, 16),
                        shape=ft.RoundedRectangleBorder(radius=16),
                    ),
                    width=float("inf"),
                ),
                ft.Container(height=30),
            ],
            expand=True,
            spacing=10,
            padding=ft.Padding(40, 0, 40, 0),
        )
        content_container.content = ft.Container(content=content, expand=True)

    render_content(countries)

    return ft.View(
        route="/onboarding",
        controls=[content_container],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=0,
    )


def _scroll_to_focused(e, scrollable):
    key = getattr(e.control, "key", None)
    if key and hasattr(scrollable, "scroll_to"):
        with contextlib.suppress(Exception):
            scrollable.scroll_to(key=key, duration=200)
