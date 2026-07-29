"""Notification utilities for app_next components."""

import flet as ft

from core.theme import AppColors


def notify(msg: str) -> None:
    """Show a SnackBar notification. Best-effort — swallow if no page."""
    from flet import context

    try:
        context.page.show_dialog(ft.SnackBar(ft.Text(msg)))
    except Exception:
        pass


def notify_warning(msg: str) -> None:
    """Show a warning SnackBar. Best-effort."""
    from flet import context

    try:
        context.page.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=AppColors.WARNING))
    except Exception:
        pass


def notify_error(msg: str) -> None:
    """Show an error SnackBar. Best-effort."""
    from flet import context

    try:
        context.page.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=AppColors.ERROR))
    except Exception:
        pass
