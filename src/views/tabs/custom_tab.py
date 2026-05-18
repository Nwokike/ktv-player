import base64
import time

import flet as ft

from core.constants import (
    ERR_ADD_CONTENT,
    LBL_ADD,
    LBL_ADD_CONTENT,
    LBL_ADDED_SUCCESS,
    LBL_CANCEL,
    LBL_NAME,
    LBL_NAME_HINT,
    LBL_PLAYLIST,
    LBL_SINGLE_CHANNEL,
    LBL_TV_FIELD_HINT,
    LBL_TYPE,
    LBL_URL,
    LBL_URL_HINT,
)
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from views.tabs import build_channel_groups, style_focusable

_dialog_refs = {"dialog": None, "name": ft.Ref[ft.TextField](), "url": ft.Ref[ft.TextField]()}
_last_add_time = 0.0
_ADD_COOLDOWN = 5.0


def build_custom_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, active_tiles):
    async def focus_field(field_ref):
        if field_ref.current:
            await field_ref.current.focus()

    def close_dialog(e_page_obj):
        e_page_obj.pop_dialog()

    def handle_type_change(e):
        view_state["add_type"] = list(e.control.selected)[0]
        e.control.update()

    async def handle_add(e):
        global _last_add_time
        now = time.time()
        if now - _last_add_time < _ADD_COOLDOWN:
            close_dialog(page_obj)
            page_obj.snack_bar = ft.SnackBar(
                ft.Text("Please wait a few seconds before adding more content."),
                bgcolor=AppColors.WARNING,
            )
            page_obj.snack_bar.open = True
            page_obj.update()
            return

        name = _dialog_refs["name"].current.value.strip()
        raw_url = _dialog_refs["url"].current.value.strip()

        if not name or not raw_url:
            return

        if len(name) > 200:
            name = name[:200]

        stealth_codes = {
            "#movies": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL21vdmllcy5tM3U=",
            "#sports": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL3Nwb3J0cy5tM3U=",
            "#news": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL25ld3MubTN1",
            "#music": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL211c2ljLm0zdQ==",
            "#kids": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL2tpZHMubTN1",
            "#comedy": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9jYXRlZ29yaWVzL2NvbWVkeS5tM3U=",
            "#global": "aHR0cHM6Ly9pcHR2LW9yZy5naXRodWIuaW8vaXB0di9pbmRleC5tM3U=",
        }
        shortcode_key = raw_url.lower()
        is_stealth = shortcode_key in stealth_codes
        final_url = (
            base64.b64decode(stealth_codes[shortcode_key]).decode("utf-8")
            if is_stealth
            else raw_url
        )

        if not is_stealth and not final_url.startswith(("http://", "https://")):
            close_dialog(page_obj)
            page_obj.snack_bar = ft.SnackBar(
                ft.Text("URL must start with http:// or https://"),
                bgcolor=AppColors.ERROR,
            )
            page_obj.snack_bar.open = True
            page_obj.update()
            return

        close_dialog(page_obj)
        refresh_tab = getattr(target, "_refresh_tab", None)

        _dialog_refs["name"].current.value = ""
        _dialog_refs["url"].current.value = ""

        state.is_loading = True
        if refresh_tab:
            refresh_tab(view_state["selected_tab"])
        page_obj.update()

        try:
            if is_stealth or view_state["add_type"] == "playlist":
                await db_manager.add_playlist(name, final_url)
            else:
                await db_manager.add_custom_channel(name, final_url)

            _last_add_time = time.time()

            if hasattr(page_obj, "load_channels"):
                await page_obj.load_channels(force=True)

            state.is_loading = False
            if refresh_tab:
                refresh_tab(view_state["selected_tab"])

            page_obj.snack_bar = ft.SnackBar(
                ft.Text(LBL_ADDED_SUCCESS.format(name=name)), bgcolor=AppColors.SUCCESS
            )
            page_obj.snack_bar.open = True
            page_obj.update()
        except Exception:
            page_obj.snack_bar = ft.SnackBar(
                ft.Text(ERR_ADD_CONTENT), bgcolor=AppColors.ERROR
            )
            page_obj.snack_bar.open = True
            page_obj.update()

    def create_tv_field(label, hint, ref, next_ref=None, is_submit=False):
        container = ft.Container(
            content=ft.Column([
                ft.Text(label, size=12, color=AppColors.GREY_DIM, weight=ft.FontWeight.W_500),
                ft.TextField(
                    ref=ref,
                    hint_text=hint,
                    border=ft.InputBorder.NONE,
                    height=40,
                    content_padding=ft.Padding(10, 0, 10, 0),
                    on_submit=lambda e: (
                        page_obj.run_task(focus_field, next_ref) if next_ref
                        else (page_obj.run_task(handle_add, e) if is_submit else None)
                    ),
                ),
            ], spacing=2),
            padding=10,
            border=ft.Border.all(1, AppColors.GREY_DIM),
            border_radius=8,
            on_click=lambda e: page_obj.run_task(focus_field, ref),
        )
        container.on_focus = lambda e: style_focusable(e.control, True)
        container.on_blur = lambda e: style_focusable(e.control, False)
        container.tab_index = 0
        return container

    if not _dialog_refs["dialog"]:
        _dialog_refs["dialog"] = ft.AlertDialog(
            title=ft.Text(LBL_ADD_CONTENT, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Text(LBL_TYPE, size=12, color=AppColors.GREY_DIM, weight=ft.FontWeight.W_500),
                    ft.SegmentedButton(
                        selected=[view_state["add_type"]],
                        allow_empty_selection=False,
                        on_change=handle_type_change,
                        segments=[
                            ft.Segment(
                                value="playlist",
                                label=ft.Text(LBL_PLAYLIST),
                                icon=ft.Icon(ft.Icons.PLAYLIST_ADD),
                            ),
                            ft.Segment(
                                value="channel",
                                label=ft.Text(LBL_SINGLE_CHANNEL),
                                icon=ft.Icon(ft.Icons.TV),
                            ),
                        ],
                    ),
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    create_tv_field(LBL_NAME, LBL_NAME_HINT, _dialog_refs["name"], next_ref=_dialog_refs["url"]),
                    create_tv_field(LBL_URL, LBL_URL_HINT, _dialog_refs["url"], is_submit=True),
                    ft.Text(
                        LBL_TV_FIELD_HINT,
                        size=11,
                        color=AppColors.GREY_DIM,
                        italic=True,
                    ),
                ],
                tight=True,
                spacing=10,
                width=500,
            ),
            actions=[
                ft.TextButton(
                    content=LBL_CANCEL,
                    on_click=lambda e: close_dialog(page_obj),
                    style=ft.ButtonStyle(padding=20)
                ),
                ft.FilledButton(
                    content=LBL_ADD,
                    on_click=handle_add,
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.PRIMARY,
                        color=ft.Colors.WHITE,
                        padding=20,
                        shape=ft.RoundedRectangleBorder(radius=8)
                    ),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    target.controls.append(
        ft.FilledButton(
            content=LBL_ADD_CONTENT,
            icon=ft.Icons.LINK,
            on_click=lambda e: page_obj.show_dialog(_dialog_refs["dialog"]),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=20,
                bgcolor=AppColors.PRIMARY,
                color=ft.Colors.WHITE,
            ),
            width=float("inf"),
        )
    )
    target.controls.append(ft.Container(height=10))
    ad_banner = ad_service.get_standard_banner_ad()
    if ad_banner:
        target.controls.append(ad_banner)
        target.controls.append(ft.Divider(height=20, color=AppColors.GREY_DIM))

    build_channel_groups(target, 2, page_obj, on_play, ad_service, liveliness, view_state, active_tiles)
