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


def build_onboarding_view(page_obj: ft.Page, on_complete: callable) -> ft.View:
    selected_state = {"country": ""}
    terms_checked = ft.Ref[ft.Checkbox]()

    def _palette() -> dict:
        return {
            "page_bg": "background",
            "surface": "surface",
            "surface_variant": "surfaceVariant",
            "text": "onSurface",
            "text_dim": "onSurfaceVariant",
            "border": "outline",
        }

    palette = _palette()

    country_list = ft.ListView(
        height=220,
        spacing=3,
        padding=ft.Padding(6, 6, 6, 6),
        auto_scroll=False,
    )

    all_country_tiles = []

    def select_country(name: str):
        selected_state["country"] = name
        for tile_info in all_country_tiles:
            is_selected = tile_info["name"] == name
            tile_info["tile"].bgcolor = AppColors.PRIMARY if is_selected else None
            tile_info["tile"].leading = ft.Icon(
                ft.Icons.CHECK_CIRCLE if is_selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
                color=ft.Colors.WHITE if is_selected else palette["text_dim"],
            )
            tile_info["tile"].title = ft.Text(
                tile_info["name"],
                color=ft.Colors.WHITE if is_selected else palette["text"],
                weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
            )
        country_list.update()

    async def _load_countries():
        from channels.provider import channel_provider
        countries_from_playlist = await channel_provider.get_all_channels()
        countries_from_playlist = channel_provider.get_countries()
        if not countries_from_playlist:
            countries_from_playlist = [{"name": "Global"}]
        countries_from_playlist.append({"name": "Other"})

        for c in countries_from_playlist:
            cname = c["name"]
            tile = ft.ListTile(
                title=ft.Text(cname, color=palette["text"], size=14),
                leading=ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, color=palette["text_dim"]),
                key=cname,
                on_click=lambda e, name=cname: select_country(name),
                dense=True,
                shape=ft.RoundedRectangleBorder(radius=12),
            )
            tile.on_focus = lambda e: _tile_focus(e, country_list)
            all_country_tiles.append({"name": cname, "tile": tile})
            country_list.controls.append(tile)
        page_obj.update()

    page_obj.run_task(_load_countries)

    country_picker_container = ft.Container(
        content=country_list,
        border=ft.Border.all(1.5, palette["border"]),
        border_radius=14,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        padding=4,
    )

    async def handle_submit(e):
        if not terms_checked.current.value:
            page_obj.snack_bar = ft.SnackBar(
                ft.Text(LBL_PLEASE_ACCEPT_TERMS),
                bgcolor=AppColors.WARNING,
            )
            page_obj.snack_bar.open = True
            page_obj.update()
            return

        country_name = selected_state["country"]
        if not country_name:
            page_obj.snack_bar = ft.SnackBar(
                ft.Text(LBL_PLEASE_SELECT_COUNTRY),
                bgcolor=AppColors.WARNING,
            )
            page_obj.snack_bar.open = True
            page_obj.update()
            return

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
                    ft.Image(src="/icon.png", width=90, height=90, border_radius=20),
                    ft.Text(
                        LBL_WELCOME,
                        size=34,
                        weight=ft.FontWeight.BOLD,
                        color=palette["text"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        LBL_WELCOME_SUB,
                        size=15,
                        text_align=ft.TextAlign.CENTER,
                        color=palette["text_dim"],
                        width=400,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            ft.Divider(height=24, color=AppColors.TRANSPARENT),
            ft.Text(
                LBL_SELECT_COUNTRY,
                size=18,
                weight=ft.FontWeight.W_600,
                color=palette["text"],
                text_align=ft.TextAlign.CENTER,
                width=float("inf"),
            ),
            ft.Text(
                LBL_TV_NAV_HINT,
                size=12,
                color=palette["text_dim"],
                text_align=ft.TextAlign.CENTER,
                width=float("inf"),
            ),
            country_picker_container,
            ft.Divider(height=20, color=AppColors.TRANSPARENT),
            ft.Container(
                content=ft.Text(
                    TERMS_TEXT,
                    size=12,
                    color=palette["text_dim"],
                    text_align=ft.TextAlign.LEFT,
                ),
                padding=16,
                bgcolor=palette["surface"],
                border_radius=12,
                border=ft.Border.all(1, palette["border"]),
            ),
            ft.Row(
                [
                    ft.Checkbox(ref=terms_checked, value=False),
                    ft.Text(
                        LBL_USAGE_AGREEMENT,
                        size=14,
                        weight=ft.FontWeight.W_500,
                        color=palette["text"],
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                wrap=True,
            ),
            ft.Divider(height=20, color=AppColors.TRANSPARENT),
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

    return ft.View(
        route="/onboarding",
        controls=[
            ft.Container(
                content=content,
                expand=True,
                bgcolor=palette["page_bg"],
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=0,
    )


def _tile_focus(e, scrollable):
    ck = getattr(e.control, "key", None)
    if ck and hasattr(scrollable, "scroll_to"):
        with contextlib.suppress(Exception):
            scrollable.scroll_to(key=ck, duration=200)
