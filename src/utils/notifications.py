"""Notification utilities using SnackBar overlay pattern."""

import asyncio
import logging

import flet as ft

from core.theme import AppColors

logger = logging.getLogger(__name__)

# Module-level state for fullscreen fallback notifications
_local_notification_state: dict = {"container": None, "text": None}

# Track pending auto-hide task so repeated notifications reset the timer
_local_hide_task = None


def register_local_notification(container, text_control):
    """Register a local notification container for fullscreen fallback."""
    _local_notification_state["container"] = container
    _local_notification_state["text"] = text_control


def unregister_local_notification():
    """Unregister local notification container and cancel pending hide."""
    _local_notification_state["container"] = None
    _local_notification_state["text"] = None
    global _local_hide_task
    if _local_hide_task and not _local_hide_task.done():
        _local_hide_task.cancel()
    _local_hide_task = None


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


def _show_local_notification(msg: str, auto_hide: bool = True) -> None:
    """Show notification in local player container (for fullscreen fallback)."""
    global _local_hide_task
    container = _local_notification_state.get("container")
    text = _local_notification_state.get("text")
    if not container or not text:
        return
    try:
        text.value = msg
        container.visible = True
        container.update()
    except Exception:
        return

    if auto_hide:
        # Cancel any pending hide, schedule a new 3-second one
        if _local_hide_task and not _local_hide_task.done():
            _local_hide_task.cancel()

        async def _hide():
            await asyncio.sleep(3.0)
            try:
                container.visible = False
                container.update()
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            _local_hide_task = loop.create_task(_hide())
        except RuntimeError:
            pass


def notify(msg: str, persist: bool = False) -> None:
    _show_snackbar(msg, persist=persist)
    _show_local_notification(msg, auto_hide=not persist)


def notify_warning(msg: str, persist: bool = False) -> None:
    _show_snackbar(msg, bgcolor=AppColors.WARNING, persist=persist)
    _show_local_notification(msg, auto_hide=not persist)


def notify_error(msg: str, persist: bool = False) -> None:
    _show_snackbar(msg, bgcolor=AppColors.ERROR, persist=persist)
    _show_local_notification(msg, auto_hide=not persist)
