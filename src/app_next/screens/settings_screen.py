"""SettingsScreen — appearance, localization, data management, about sections.

Uses ExpansionTile for inline reveal instead of modal dialogs.
"""

import asyncio

import flet as ft
from flet.controls.control import Control

from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from app_next.utils.notifications import notify, notify_warning
from app_next.utils.theme_utils import toggle_theme as _toggle_theme_util
from channels.provider import channel_provider
from core.constants import (
    APP_VERSION,
    LBL_CLEAR_HISTORY,
    LBL_CLEAR_HISTORY_DESC,
    LBL_COUNTRY_UPDATED,
    LBL_HISTORY_CLEARED,
    LBL_LIBRARY_RESET,
    LBL_RESET_LIBRARY,
    LBL_RESET_LIBRARY_DESC,
)
from core.logger_handler import MemoryLogHandler
from core.state import state as core_state
from core.theme import AppColors
from database.manager import db_manager

_SECTIONS = [
    {"key": "appearance", "icon": ft.Icons.PALETTE, "title": "Appearance"},
    {"key": "localization", "icon": ft.Icons.PUBLIC, "title": "Localization"},
    {"key": "data_management", "icon": ft.Icons.STORAGE, "title": "Data Management"},
    {"key": "custom_content", "icon": ft.Icons.PLAYLIST_ADD, "title": "Custom Content"},
    {"key": "about", "icon": ft.Icons.INFO, "title": "About"},
]


_notify = notify
_notify_warning = notify_warning


@ft.component
def SettingsScreen() -> Control:
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    is_clearing, set_is_clearing = ft.use_state(False)
    is_resetting, set_is_resetting = ft.use_state(False)

    async def _clear_history():
        set_is_clearing(True)
        try:
            await db_manager.clear_history()
            core_state.history.clear()
            _notify(LBL_HISTORY_CLEARED)
        except Exception:
            _notify_warning("Failed to clear history.")
        finally:
            set_is_clearing(False)

    async def _reset_custom():
        set_is_resetting(True)
        try:
            await db_manager.clear_custom_content()
            _notify(LBL_LIBRARY_RESET)
            await controller.refresh_channels()
        except Exception:
            _notify_warning("Failed to reset custom content.")
        finally:
            set_is_resetting(False)

    def _update_country(country_name: str):
        async def _do():
            await db_manager.set_setting("user_country", country_name)
            core_state.user_country = country_name
            _notify(LBL_COUNTRY_UPDATED.format(country=country_name))

        asyncio.create_task(_do())

    def _is_dark() -> bool:
        from flet.controls.context import context

        from core.theme import AppColors

        return AppColors._is_dark(context.page)

    def _toggle_theme(e):
        from flet.controls.context import context

        _toggle_theme_util(context.page)

    # --- Section content builders ---

    def _appearance_content() -> Control:
        return ft.Row(
            controls=[
                ft.Text("Dark Mode"),
                ft.Switch(value=_is_dark(), on_change=_toggle_theme, autofocus=True),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _localization_content() -> Control:
        countries = channel_provider.get_countries()
        country_names = [c.get("name", "") for c in countries if c.get("name")] or [
            "Nigeria",
            "Ghana",
            "USA",
            "UK",
            "Other",
        ]
        current = state.user_country or "Not set"
        items = [
            ft.Text(f"Current: {current}", size=12, color=ft.Colors.GREY, italic=True)
        ]
        for name in country_names:
            is_selected = name == state.user_country
            items.append(
                ft.ListTile(
                    title=ft.Text(name),
                    trailing=ft.Icon(ft.Icons.CHECK, color=AppColors.PRIMARY)
                    if is_selected
                    else None,
                    on_click=lambda e, n=name: _update_country(n),
                    dense=True,
                )
            )
        return ft.Column(items, spacing=2)

    def _data_content() -> Control:
        return ft.Column(
            controls=[
                ft.ListTile(
                    title=ft.Text(LBL_CLEAR_HISTORY),
                    subtitle=ft.Text(LBL_CLEAR_HISTORY_DESC),
                    dense=True,
                ),
                ft.FilledButton(
                    content=ft.Text("Clearing..." if is_clearing else "Clear History"),
                    disabled=is_clearing,
                    on_click=lambda e: asyncio.create_task(_clear_history()),
                ),
                ft.Divider(height=8),
                ft.ListTile(
                    title=ft.Text(LBL_RESET_LIBRARY),
                    subtitle=ft.Text(LBL_RESET_LIBRARY_DESC),
                    dense=True,
                ),
                ft.FilledButton(
                    content=ft.Text("Resetting..." if is_resetting else "Reset Library"),
                    disabled=is_resetting,
                    on_click=lambda e: asyncio.create_task(_reset_custom()),
                ),
            ],
            spacing=4,
        )

    def _logs_content() -> Control:
        logs = MemoryLogHandler.get_logs()
        log_text = "\n".join(logs) if logs else "No activity logs recorded yet."
        log_control = ft.Text(
            value=log_text,
            size=11,
            font_family="monospace",
            color=AppColors.SUCCESS,
            selectable=True,
        )
        return ft.Column(
            controls=[
                ft.Container(
                    content=ft.ListView(
                        controls=[log_control], auto_scroll=True, height=250
                    ),
                    bgcolor=ft.Colors.BLACK87,
                    border_radius=8,
                    padding=8,
                ),
                ft.Row(
                    controls=[
                        ft.TextButton(
                            "Copy Logs",
                            on_click=lambda e: _copy_logs(log_control.value),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
            ],
            spacing=4,
        )

    def _about_content() -> Control:
        import sys

        return ft.Column(
            controls=[
                ft.Text(f"Version: {APP_VERSION}", size=14),
                ft.Text(
                    f"Framework: Flet {ft.__version__} + mpv",
                    size=12,
                    color=ft.Colors.GREY,
                ),
                ft.Text(
                    f"Built with Python {sys.version.split()[0]}",
                    size=12,
                    color=ft.Colors.GREY,
                ),
                ft.Divider(height=1),
                ft.Text("An IPTV rendering engine and local media player.", size=12),
            ],
            spacing=6,
        )

    # --- Build section ExpansionTiles ---
    content_builders = {
        "appearance": _appearance_content,
        "localization": _localization_content,
        "data_management": _data_content,
        "custom_content": _logs_content,
        "about": _about_content,
    }

    tiles: list[Control] = []
    for idx, section in enumerate(_SECTIONS):
        tile = ft.ExpansionTile(
            leading=ft.Icon(section["icon"]),
            title=ft.Text(section["title"]),
            controls=[content_builders[section["key"]]()],
            dense=True,
            expanded=idx == 0,
        )
        tiles.append(tile)
        tiles.append(ft.Divider(height=1))

    return ft.ListView(controls=tiles, expand=True, spacing=4, padding=10)


def _copy_logs(text: str):
    async def _do():
        try:
            await ft.Clipboard().set(text)
        except Exception:
            pass

    asyncio.create_task(_do())
