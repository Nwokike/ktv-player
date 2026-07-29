"""Theme toggling utility for app_next components."""

import asyncio

import flet as ft

from database.manager import db_manager


def toggle_theme(page: ft.Page) -> None:
    """Toggle between light and dark theme and persist to DB."""
    from core.theme import AppColors

    is_dark = AppColors._is_dark(page)
    new_mode = ft.ThemeMode.LIGHT if is_dark else ft.ThemeMode.DARK
    page.theme_mode = new_mode
    page.update()

    async def _save():
        await db_manager.set_setting(
            "theme_mode", "dark" if new_mode == ft.ThemeMode.DARK else "light"
        )

    asyncio.create_task(_save())
