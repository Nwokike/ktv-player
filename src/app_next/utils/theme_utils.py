"""Theme toggling utility."""

import asyncio
import logging

import flet as ft

from database.manager import db_manager

logger = logging.getLogger(__name__)


def toggle_theme(page: ft.Page) -> None:
    """Toggle between light and dark theme and persist to DB."""
    from core.theme import AppColors

    is_dark = AppColors._is_dark(page)
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
        loop.create_task(_save())
    except RuntimeError:
        pass
