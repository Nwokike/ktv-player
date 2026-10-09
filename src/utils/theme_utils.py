"""Theme toggling utility."""

import asyncio
import logging

import flet as ft

from database.manager import db_manager

logger = logging.getLogger(__name__)


_save_task: asyncio.Task | None = None


def toggle_theme(page: ft.Page) -> None:
    """Toggle between light and dark theme and persist to DB."""
    global _save_task
    from core.theme import AppColors

    is_dark = AppColors.is_dark(page)
    new_mode = ft.ThemeMode.LIGHT if is_dark else ft.ThemeMode.DARK
    page.theme_mode = new_mode
    page.update()

    async def _save():
        try:
            await db_manager.set_setting(
                "theme_mode", "dark" if new_mode == ft.ThemeMode.DARK else "light"
            )
        except Exception:
            logger.exception("Failed to persist theme mode")

    try:
        loop = asyncio.get_running_loop()
        # Cancel a still-pending save so a fast double-toggle writes the
        # FINAL mode, not the intermediate one (same missing-reference
        # class of bug the toast-hide timer had).
        if _save_task is not None and not _save_task.done():
            _save_task.cancel()
        _save_task = loop.create_task(_save())
        _save_task.add_done_callback(lambda t: _drop_save_ref(t))
    except RuntimeError:
        pass


def _drop_save_ref(task: asyncio.Task) -> None:
    global _save_task
    if _save_task is task:
        _save_task = None
