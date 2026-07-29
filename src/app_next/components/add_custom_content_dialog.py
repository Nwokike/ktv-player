"""AddCustomContentDialog — modal for adding M3U playlist or single channel.

Uses use_effect to call page.show_dialog() when open=True, instead of
returning the AlertDialog in the control tree. This is required because
DialogControl (AlertDialog) must be rendered via the page overlay, not
embedded in a Column.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

import flet as ft
from flet.controls.control import Control

from app_next.hooks.use_storage import use_storage
from app_next.state.controller_ctx import ControllerMethodsCtx
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
from core.theme import AppColors

# --- pure helpers (exported for unit tests) ---


def _is_valid_url(url: str) -> bool:
    stripped = url.strip()
    return (
        stripped.startswith(("http://", "https://", "HTTP://", "HTTPS://"))
        and len(stripped) > 7
    )


def _can_add(name: str, url: str, last_add_time: float) -> bool:
    if not name.strip():
        return False
    if len(name.strip()) > MAX_NAME_LENGTH:
        return False
    if not _is_valid_url(url):
        return False
    if last_add_time > 0:
        return (time.time() - last_add_time) >= ADD_CONTENT_COOLDOWN
    return True


def _format_name(name: str, add_type: str) -> str:
    stripped = name.strip()
    if not stripped:
        return "Unnamed Playlist" if add_type == "playlist" else "Unnamed Channel"
    return stripped


@ft.component
def AddCustomContentDialog(
    open: bool,
    on_close: Callable[[], None],
    on_added: Callable[[], Awaitable[None] | None],
) -> Control:
    """Render a dialog for adding custom content when `open` is True.

    Uses use_effect to call page.show_dialog() — the AlertDialog lives
    in the page overlay, not in the control tree.
    """
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
            _dismiss()
            result = on_added()
            if hasattr(result, "__await__"):
                asyncio.create_task(result)
        except Exception:
            _notify_warning("Failed to add content.")
        finally:
            set_is_adding(False)

    async def _handle_cancel(e):
        _reset()
        await _dismiss()
        on_close()

    async def _dismiss():
        from flet.controls.context import context

        try:
            context.page.pop_dialog()
        except Exception:
            pass
        if controller is not None:
            await controller.close_modal()

    async def _show():
        from flet.controls.context import context

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
                    ft.TextField(
                        label=LBL_NAME,
                        hint_text=LBL_NAME_HINT,
                        value=name,
                        on_change=lambda e: set_name(e.control.value),
                        max_length=MAX_NAME_LENGTH,
                        autofocus=True,
                    ),
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
            on_dismiss=lambda: (
                asyncio.create_task(
                    controller.close_modal() if controller else asyncio.sleep(0)
                )
                or on_close()
            ),
        )
        if controller is not None:
            await controller.push_modal("add_content")
        try:
            context.page.show_dialog(dialog)
        except Exception:
            pass

    ft.use_effect(_show, [open])

    return ft.Container(height=0, visible=False)


def _notify_success(msg: str) -> None:
    from flet.controls.context import context

    try:
        context.page.show_dialog(ft.SnackBar(ft.Text(msg)))
    except Exception:
        pass


def _notify_warning(msg: str) -> None:
    from flet.controls.context import context

    try:
        context.page.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=AppColors.WARNING))
    except Exception:
        pass
