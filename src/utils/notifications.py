"""Notification utilities using SnackBar overlay pattern."""

import flet as ft

from core.theme import AppColors

# Module-level state for fullscreen fallback notifications
_local_notification_state: dict = {"container": None, "text": None}


def register_local_notification(container, text_control):
    """Register a local notification container for fullscreen fallback."""
    _local_notification_state["container"] = container
    _local_notification_state["text"] = text_control


def unregister_local_notification():
    """Unregister local notification container."""
    _local_notification_state["container"] = None
    _local_notification_state["text"] = None


def _get_local_notification_state():
    """Get current local notification state."""
    return _local_notification_state["container"], _local_notification_state["text"]


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
            margin=ft.Margin(16, 0, 16, 80),
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()
    except Exception:
        pass


def _show_local_notification(msg: str) -> None:
    """Show notification in local player container (for fullscreen fallback)."""
    container, text = _get_local_notification_state()
    if container and text:
        try:
            text.value = msg
            container.visible = True
            container.update()
        except Exception:
            pass


def notify(msg: str) -> None:
    _show_snackbar(msg, persist=True)
    _show_local_notification(msg)


def notify_warning(msg: str) -> None:
    _show_snackbar(msg, bgcolor=AppColors.WARNING, persist=True)
    _show_local_notification(msg)


def notify_error(msg: str) -> None:
    _show_snackbar(msg, bgcolor=AppColors.ERROR, persist=True)
    _show_local_notification(msg)
