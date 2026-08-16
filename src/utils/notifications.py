"""Notification utilities using SnackBar overlay pattern.

While a video is in native fullscreen, SnackBars are invisible: media_kit
pushes an opaque fullscreen route on the ROOT navigator, which sits above
Flet's entire page tree (views, page.overlay and dialogs). The only
Flet-rendered surface inside fullscreen is the video's own controls
(flet_video re-renders the same `Video.controls` there, per
VideoControlsMode). ImmersivePlayer therefore registers its in-controls
toast chip here and flips the active flag from on_enter/exit_fullscreen.
"""

import asyncio
import logging

import flet as ft

from core.theme import AppColors

logger = logging.getLogger(__name__)

# In-player toast chip used while the player is in native fullscreen.
_fullscreen_toast: dict = {
    "container": None,
    "text": None,
    "active": False,
}

_hide_task: asyncio.Task | None = None
_TOAST_HIDE_AFTER = 3.0


def register_fullscreen_toast(container, text_control) -> None:
    """Register the player's in-controls toast chip (visible in fullscreen)."""
    _fullscreen_toast.update(container=container, text=text_control, active=False)


def unregister_fullscreen_toast() -> None:
    """Drop the chip registration and cancel any pending auto-hide."""
    _fullscreen_toast.update(container=None, text=None, active=False)
    _cancel_hide_task()


def set_fullscreen_toast_active(active: bool) -> None:
    """Track whether the player is currently in native fullscreen."""
    _fullscreen_toast["active"] = active
    if not active:
        _cancel_hide_task()
        _hide_toast()


def _cancel_hide_task():
    global _hide_task
    if _hide_task and not _hide_task.done():
        _hide_task.cancel()
    _hide_task = None


def _hide_toast():
    container = _fullscreen_toast.get("container")
    if not container:
        return
    try:
        container.visible = False
        container.update()
    except Exception:
        pass


def _show_snackbar(msg: str, bgcolor=None, persist: bool = False) -> None:
    """Show a SnackBar via page.overlay. Best-effort."""
    from flet import context

    try:
        page = context.page
        snack = ft.SnackBar(
            content=ft.Text(msg),
            bgcolor=bgcolor,
            show_close_icon=True,
            behavior=ft.SnackBarBehavior.FLOATING,
            dismiss_direction=ft.DismissDirection.HORIZONTAL,
            persist=persist,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()
    except Exception:
        pass


def _show_fullscreen_toast(msg: str) -> bool:
    """Show msg in the player's in-controls toast chip.

    Returns True when the chip was updated, False when it is not mounted
    (caller falls back to the SnackBar).
    """
    container = _fullscreen_toast.get("container")
    text = _fullscreen_toast.get("text")
    if not container or not text:
        return False

    try:
        text.value = msg
        container.visible = True
        container.update()
    except Exception:
        return False

    # Reset any pending hide, then schedule a fresh one
    _cancel_hide_task()

    async def _hide():
        await asyncio.sleep(_TOAST_HIDE_AFTER)
        _hide_toast()

    try:
        loop = asyncio.get_running_loop()
        _hide_task = loop.create_task(_hide())
    except RuntimeError:
        pass
    return True


def _dispatch(msg: str, bgcolor=None, persist: bool = False) -> None:
    """Route to the fullscreen toast chip when active, else the SnackBar."""
    if _fullscreen_toast["active"] and _show_fullscreen_toast(msg):
        return
    _show_snackbar(msg, bgcolor=bgcolor, persist=persist)


def notify(msg: str, persist: bool = False) -> None:
    _dispatch(msg, persist=persist)


def notify_warning(msg: str, persist: bool = False) -> None:
    _dispatch(msg, bgcolor=AppColors.WARNING, persist=persist)


def notify_error(msg: str, persist: bool = False) -> None:
    _dispatch(msg, bgcolor=AppColors.ERROR, persist=persist)
