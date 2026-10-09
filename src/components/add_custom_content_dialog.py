"""AddCustomContentDialog — modal for adding M3U playlist or single channel."""

import logging
import time
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

import flet as ft
from flet import Control, use_dialog

from core.constants import (
    ADD_CONTENT_COOLDOWN,
    ERR_ADD_CONTENT,
    LBL_NAME,
    LBL_NAME_HINT,
    LBL_PLAYLIST,
    LBL_SINGLE_CHANNEL,
    LBL_TYPE,
    LBL_URL,
    LBL_URL_HINT,
    MAX_NAME_LENGTH,
)
from hooks.use_storage import use_storage
from state.controller_ctx import ControllerMethodsCtx
from utils.notifications import notify, notify_warning

logger = logging.getLogger(__name__)


def _is_valid_url(url: str) -> bool:
    """Non-blank http(s) URL with a host — parsed, not prefix-matched."""
    stripped = url.strip()
    if not stripped:
        return False
    try:
        parsed = urlparse(stripped)
    except ValueError:
        return False
    return parsed.scheme.lower() in ("http", "https") and bool(parsed.hostname)


def _can_add(
    url: str, last_add_time: float, name: str = "", add_type: str = "playlist"
) -> bool:
    if add_type == "channel" and not name.strip():
        return False
    if not _is_valid_url(url):
        return False
    if last_add_time > 0:
        return (time.time() - last_add_time) >= ADD_CONTENT_COOLDOWN
    return True


def _cooldown_hint(last_add_time: float) -> str:
    """Human countdown for the disabled Add button, "" when cooled down."""
    remaining = ADD_CONTENT_COOLDOWN - (time.time() - last_add_time)
    if last_add_time > 0 and remaining > 0:
        return f"Wait {remaining:.0f}s before adding again"
    return ""


def _default_playlist_name(url: str) -> str:
    """URL-derived playlist name: basename without query/fragment/ext.

    Falls back to "Playlist" when the URL carries no usable basename.
    """
    try:
        path = urlparse(url.strip()).path.rstrip("/")
        base = path.rsplit("/", 1)[-1] if path else ""
        base = base.rsplit(".", 1)[0] if "." in base else base
        return base.strip() or "Playlist"
    except ValueError:
        return "Playlist"


@ft.component
def AddCustomContentDialog(
    open: bool,
    on_close: Callable[[], None],
    on_added: Callable[[], Awaitable[None] | None],
) -> Control:
    # All hooks first, unconditionally — conditional use_state/use_context
    # after an early return would shift hook order between renders.
    add_type, set_add_type = ft.use_state("playlist")
    name, set_name = ft.use_state("")
    url, set_url = ft.use_state("")
    last_add, set_last_add = ft.use_state(0.0)
    is_adding, set_is_adding = ft.use_state(False)
    url_error, set_url_error = ft.use_state("")
    in_flight = ft.use_ref(False)
    modal_pushed = ft.use_ref(False)
    storage = use_storage()
    controller = ft.use_context(ControllerMethodsCtx)

    def _reset():
        set_name("")
        set_url("")
        set_add_type("playlist")
        set_url_error("")
        # Cooldown timestamp is intentionally NOT cleared here: _reset runs
        # after every successful add, and clearing would disable the
        # double-submit guard. Fresh-mount state starts at 0.0.

    async def _handle_add(e):
        if in_flight.current:
            return
        trimmed_url = url.strip()
        if add_type == "channel" and not name.strip():
            set_url_error("Give the channel a name first.")
            return
        if not _is_valid_url(trimmed_url):
            set_url_error(
                "Enter a full http(s) link — it usually ends in .m3u or .m3u8."
            )
            return
        if not _can_add(trimmed_url, last_add, name, add_type):
            hint = _cooldown_hint(last_add)
            set_url_error(hint or "Please wait before adding again.")
            return
        in_flight.current = True
        set_is_adding(True)
        set_url_error("")
        try:
            if add_type == "playlist":
                await storage.add_playlist(
                    _default_playlist_name(trimmed_url), trimmed_url
                )
                _notify_success(
                    "✅ Playlist added! Select 'Custom' in the filter bar to view your channels."
                )
            else:
                final_name = name.strip() or "Channel"
                await storage.add_custom_channel(final_name, trimmed_url)
                _notify_success(
                    "✅ Channel added! Select 'Custom' in the filter bar to view it."
                )
            set_last_add(time.time())
            _reset()
            on_close()
            try:
                result = on_added()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                logger.exception("Add-content on_added callback failed")
        except Exception:
            logger.exception("Failed to add custom content")
            _notify_warning(ERR_ADD_CONTENT)
        finally:
            in_flight.current = False
            set_is_adding(False)

    async def _handle_cancel(e):
        _reset()
        on_close()

    def _on_segment_change(e):
        try:
            selected = e.control.selected
        except AttributeError:
            logger.debug("Segment change without selection", exc_info=True)
            return
        if selected:
            set_add_type(selected[0])

    def _on_url_change(e):
        set_url(e.control.value)
        if url_error:
            set_url_error("")

    dialog: Control | None = None
    if open:
        # URL field — Enter submits the dialog
        url_field = ft.TextField(
            label=LBL_URL,
            hint_text=LBL_URL_HINT,
            value=url,
            on_change=_on_url_change,
            on_submit=_handle_add,
            autofocus=True,
            max_length=2048,
            error=url_error or None,
        )

        # Name field — only for single channels; Enter moves focus to URL field
        name_field = None
        if add_type == "channel":

            async def _on_name_submit(e):
                await url_field.focus()

            name_field = ft.TextField(
                label=LBL_NAME,
                hint_text=LBL_NAME_HINT,
                value=name,
                on_change=lambda e: set_name(e.control.value),
                on_submit=_on_name_submit,
                max_length=MAX_NAME_LENGTH,
            )

        hint = _cooldown_hint(last_add)
        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Custom Content"),
            content=ft.Column(
                controls=[
                    ft.Text(LBL_TYPE, size=14, weight=ft.FontWeight.W_600),
                    ft.SegmentedButton(
                        selected=[add_type],
                        on_change=_on_segment_change,
                        segments=[
                            ft.Segment(value="playlist", label=ft.Text(LBL_PLAYLIST)),
                            ft.Segment(
                                value="channel", label=ft.Text(LBL_SINGLE_CHANNEL)
                            ),
                        ],
                        allow_empty_selection=False,
                        allow_multiple_selection=False,
                    ),
                    *([name_field] if name_field else []),
                    url_field,
                    *(
                        [ft.Text(hint, size=11, italic=True)]
                        if hint and not _can_add(url, last_add, name, add_type)
                        else []
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
                    disabled=not _can_add(url, last_add, name, add_type) or is_adding,
                ),
            ],
            on_dismiss=lambda e: on_close(),
        )

    use_dialog(dialog)

    async def _sync_modal_stack():
        if open and not modal_pushed.current and controller is not None:
            modal_pushed.current = True
            try:
                await controller.push_modal("add_content")
            except Exception:
                logger.debug("add_content push_modal failed", exc_info=True)
                modal_pushed.current = False
        elif (not open) and modal_pushed.current and controller is not None:
            modal_pushed.current = False
            try:
                await controller.close_modal()
            except Exception:
                logger.debug("add_content close_modal failed", exc_info=True)

    ft.use_effect(_sync_modal_stack, [open])

    async def _cleanup_modal_stack():
        if modal_pushed.current and controller is not None:
            modal_pushed.current = False
            try:
                await controller.close_modal()
            except Exception:
                logger.debug("add_content unmount cleanup failed", exc_info=True)

    ft.use_effect(lambda: None, [], _cleanup_modal_stack)

    return ft.Container(height=0, visible=False)


_notify_success = notify
_notify_warning = notify_warning
