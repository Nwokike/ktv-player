"""Notification utilities using SnackBar overlay pattern."""

import flet as ft

from core.theme import AppColors


def _show_snackbar(msg: str, bgcolor=None) -> None:
    """Show a SnackBar via page.overlay. Best-effort."""
    from flet import context

    try:
        page = context.page
        snack = ft.SnackBar(
            content=ft.Text(msg),
            bgcolor=bgcolor,
            show_close_icon=True,
        )
        page.overlay.append(snack)
        snack.open = True
        page.update()
    except Exception:
        pass


def notify(msg: str) -> None:
    _show_snackbar(msg)


def notify_warning(msg: str) -> None:
    _show_snackbar(msg, bgcolor=AppColors.WARNING)


def notify_error(msg: str) -> None:
    _show_snackbar(msg, bgcolor=AppColors.ERROR)
