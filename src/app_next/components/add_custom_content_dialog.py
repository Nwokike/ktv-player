"""AddCustomContentDialog — modal for adding M3U playlist or single channel."""

import asyncio
import time
from collections.abc import Awaitable, Callable

import flet as ft
from flet import Control, use_dialog

from app_next.hooks.use_storage import use_storage
from app_next.state.controller_ctx import ControllerMethodsCtx
from app_next.utils.notifications import notify, notify_warning
from core.constants import (
    ADD_CONTENT_COOLDOWN,
    LBL_ADDED_SUCCESS,
    LBL_NAME,
    LBL_NAME_HINT,
    LBL_PLAYLIST,
    LBL_SINGLE_CHANNEL,
    LBL_TYPE,
    LBL_URL,
    LBL_URL_HINT,
    MAX_NAME_LENGTH,
)


def _is_valid_url(url: str) -> bool:
    stripped = url.strip()
    return (
        stripped.startswith(("http://", "https://", "HTTP://", "HTTPS://"))
        and len(stripped) > 7
    )


def _can_add(name: str, url: str, last_add_time: float) -> bool:
    if not _is_valid_url(url):
        return False
    if last_add_time > 0:
        return (time.time() - last_add_time) >= ADD_CONTENT_COOLDOWN
    return True


def _format_name(name: str, add_type: str) -> str:
    stripped = name.strip()
    if not stripped:
        return "Unnamed Channel" if add_type == "channel" else "Playlist"
    return stripped


@ft.component
def AddCustomContentDialog(
    open: bool,
    on_close: Callable[[], None],
    on_added: Callable[[], Awaitable[None] | None],
) -> Control:
    add_type, set_add_type = ft.use_state("playlist")
    name, set_name = ft.use_state("")
    url, set_url = ft.use_state("")
    last_add, set_last_add = ft.use_state(0.0)
    is_adding, set_is_adding = ft.use_state(False)
    storage = use_storage()
    controller = ft.use_context(ControllerMethodsCtx)

    def _reset():
        set_name("")
        set_url("")
        set_add_type("playlist")
        set_last_add(0.0)

    async def _handle_add(e):
        if is_adding or not _can_add(name, url, last_add):
            return
        set_is_adding(True)
        try:
            final_name = _format_name(name, add_type)
            final_url = url.strip()
            if add_type == "playlist":
                await storage.add_playlist(final_name, final_url)
            else:
                await storage.add_custom_channel(final_name, final_url)
            _notify_success(LBL_ADDED_SUCCESS.format(name=final_name))
            set_last_add(time.time())
            _reset()
            on_close()
            result = on_added()
            if hasattr(result, "__await__"):
                asyncio.create_task(result)
        except Exception:
            _notify_warning("Failed to add content.")
        finally:
            set_is_adding(False)

    async def _handle_cancel(e):
        _reset()
        on_close()

    dialog: Control | None = None
    if open:
        # Name field only shown for single channels — playlists get M3U groups automatically
        name_field = (
            [
                ft.TextField(
                    label=LBL_NAME,
                    hint_text=LBL_NAME_HINT,
                    value=name,
                    on_change=lambda e: set_name(e.control.value),
                    max_length=MAX_NAME_LENGTH,
                ),
            ]
            if add_type == "channel"
            else []
        )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Custom Content"),
            content=ft.Column(
                controls=[
                    ft.Text(LBL_TYPE, size=14, weight=ft.FontWeight.W_600),
                    ft.SegmentedButton(
                        selected=[add_type],
                        on_change=lambda e: set_add_type(e.control.selected[0]),
                        segments=[
                            ft.Segment(value="playlist", label=ft.Text(LBL_PLAYLIST)),
                            ft.Segment(
                                value="channel", label=ft.Text(LBL_SINGLE_CHANNEL)
                            ),
                        ],
                    ),
                    *name_field,
                    ft.TextField(
                        label=LBL_URL,
                        hint_text=LBL_URL_HINT,
                        value=url,
                        on_change=lambda e: set_url(e.control.value),
                    ),
                ],
                width=350,
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=_handle_cancel),
                ft.FilledButton(
                    content=ft.Text("Add Content"),
                    on_click=_handle_add,
                    disabled=not _can_add(name, url, last_add) or is_adding,
                ),
            ],
            on_dismiss=lambda: on_close(),
        )

    use_dialog(dialog)

    has_pushed, set_has_pushed = ft.use_state(False)

    async def _sync_modal_stack():
        if open and not has_pushed and controller is not None:
            set_has_pushed(True)
            await controller.push_modal("add_content")
        elif (not open) and has_pushed and controller is not None:
            set_has_pushed(False)
            await controller.close_modal()

    ft.use_effect(_sync_modal_stack, [open])

    return ft.Container(height=0, visible=False)


_notify_success = notify
_notify_warning = notify_warning
