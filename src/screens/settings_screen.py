"""SettingsScreen — modern Material 3 grouped settings."""

import asyncio
import logging

import flet as ft
from flet import Control

from channels.provider import channel_provider
from core.constants import (
    APP_NAME,
    APP_VERSION,
    ERR_CLEAR_HISTORY_FAILED,
    ERR_RESET_LIBRARY_FAILED,
    LBL_ACTIVITY_TERMINAL,
    LBL_CLEAR,
    LBL_CLEAR_HISTORY,
    LBL_CLEAR_HISTORY_DESC,
    LBL_CLEARING,
    LBL_CLOSE,
    LBL_COPY_TO_CLIPBOARD,
    LBL_COUNTRY_UPDATED,
    LBL_DARK_MODE,
    LBL_DARK_MODE_DESC,
    LBL_DEFAULT_REGION,
    LBL_FILTER_BY_COUNTRY,
    LBL_HISTORY_CLEARED,
    LBL_LIBRARY_RESET,
    LBL_LIVE_ACTIVITY_TERMINAL,
    LBL_LOG_CLEARED,
    LBL_LOG_COPIED,
    LBL_NO_ACTIVITY_LOG,
    LBL_OPEN_TERMINAL,
    LBL_RESET_LIBRARY,
    LBL_RESET_LIBRARY_DESC,
    LBL_RESETTING,
    LBL_TERMINAL_DESC,
    LBL_USAGE_AGREEMENT_BUTTON,
    LBL_USAGE_AGREEMENT_TITLE,
    TERMS_TEXT,
)
from core.logger_handler import MemoryLogHandler
from core.state import state as core_state
from core.theme import AppColors
from database.manager import db_manager
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx
from utils.notifications import notify, notify_warning
from utils.theme_utils import toggle_theme as _toggle_theme_util

logger = logging.getLogger("SettingsScreen")

_SECTIONS = [
    {"key": "appearance", "title": "Appearance", "icon": ft.Icons.PALETTE},
    {"key": "localization", "title": "Localization", "icon": ft.Icons.PUBLIC},
    {"key": "data_management", "title": "Data Management", "icon": ft.Icons.STORAGE},
    {"key": "custom_content", "title": "Development", "icon": ft.Icons.TERMINAL},
    {"key": "about", "title": "About", "icon": ft.Icons.INFO},
]


# ---------------------------------------------------------------------------
# Log terminal dialog
# ---------------------------------------------------------------------------


def _build_logs_dialog(page: ft.Page) -> ft.AlertDialog:
    logs = MemoryLogHandler.get_logs()
    logs_str = "\n".join(logs) if logs else LBL_NO_ACTIVITY_LOG

    log_text = ft.Text(
        value=logs_str,
        font_family="Courier New",
        size=12,
        color=AppColors.TERMINAL_TEXT,
        selectable=True,
    )

    async def _copy(e=None):
        try:
            await ft.Clipboard().set(log_text.value)
            notify(LBL_LOG_COPIED)
        except Exception:
            pass

    def _clear(e=None):
        MemoryLogHandler.clear_logs()
        log_text.value = LBL_LOG_CLEARED
        page.update()

    return ft.AlertDialog(
        title=ft.Text(LBL_LIVE_ACTIVITY_TERMINAL, weight=ft.FontWeight.BOLD),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(LBL_TERMINAL_DESC, size=12, color=AppColors.grey_dim()),
                    ft.Container(
                        content=ft.Column(
                            controls=[log_text],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        bgcolor=AppColors.TERMINAL_BG,
                        border=ft.Border.all(
                            1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)
                        ),
                        border_radius=8,
                        padding=12,
                        expand=True,
                    ),
                ],
                spacing=8,
            ),
            width=480,
            height=400,
        ),
        actions=[
            ft.TextButton(
                LBL_COPY_TO_CLIPBOARD,
                icon=ft.Icons.COPY,
                on_click=lambda e: asyncio.create_task(_copy()),
            ),
            ft.TextButton(LBL_CLEAR, icon=ft.Icons.DELETE_SWEEP, on_click=_clear),
            ft.TextButton(LBL_CLOSE, on_click=lambda e: page.pop_dialog()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )


# ---------------------------------------------------------------------------
# Reusable setting row
# ---------------------------------------------------------------------------


def _setting_row(
    leading: Control,
    title: str,
    subtitle: str,
    trailing: Control,
) -> ft.Container:
    """A single-line setting: [icon+text] ---- [control]."""
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        leading,
                        ft.Column(
                            controls=[
                                ft.Text(title, size=13, weight=ft.FontWeight.W_500),
                                ft.Text(subtitle, size=11, color=AppColors.grey_dim()),
                            ],
                            spacing=1,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    expand=True,
                ),
                trailing,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(4, 10, 4, 10),
    )


def _section_card(title: str, icon: str, items: list[Control]) -> ft.Container:
    """A grouped settings card with header + divider + rows."""
    from flet import context

    page = context.page
    card_bg = AppColors.get_card_bg(page)
    border_color = AppColors.get_border_color(page)

    rows: list[Control] = []
    for i, item in enumerate(items):
        rows.append(item)
        if i < len(items) - 1:
            rows.append(
                ft.Divider(
                    height=1, color=border_color, leading_indent=44, trailing_indent=0
                )
            )

    return ft.Container(
        bgcolor=card_bg,
        border=ft.Border.all(1, border_color),
        border_radius=16,
        padding=ft.Padding(16, 8, 16, 8),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(icon, color=AppColors.PRIMARY, size=20),
                        ft.Text(title, size=14, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=10,
                ),
                *rows,
            ],
            spacing=0,
        ),
    )


# ---------------------------------------------------------------------------
# Main screen
# ---------------------------------------------------------------------------


@ft.component
def SettingsScreen() -> Control:
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)
    is_clearing, set_is_clearing = ft.use_state(False)
    is_resetting, set_is_resetting = ft.use_state(False)
    _theme_mode, set_theme_mode = ft.use_state(
        lambda: AppColors._is_dark(ft.context.page)
    )

    # -- handlers --

    def _is_dark() -> bool:
        from flet import context

        return AppColors._is_dark(context.page)

    def _toggle_theme(e):
        from flet import context

        _toggle_theme_util(context.page)
        set_theme_mode(AppColors._is_dark(context.page))

    def _on_country_select(name: str):
        async def _do():
            await db_manager.set_setting("user_country", name)
            core_state.user_country = name
            notify(LBL_COUNTRY_UPDATED.format(country=name))

        asyncio.create_task(_do())

    async def _clear_history():
        set_is_clearing(True)
        try:
            await db_manager.clear_history()
            core_state.history.clear()
            notify(LBL_HISTORY_CLEARED)
        except Exception:
            notify_warning(ERR_CLEAR_HISTORY_FAILED)
        finally:
            set_is_clearing(False)

    async def _reset_custom():
        set_is_resetting(True)
        try:
            await db_manager.clear_custom_content()
            notify(LBL_LIBRARY_RESET)
            await controller.refresh_channels()
        except Exception:
            notify_warning(ERR_RESET_LIBRARY_FAILED)
        finally:
            set_is_resetting(False)

    def _open_terminal(e):
        from flet import context

        context.page.show_dialog(_build_logs_dialog(context.page))

    def _show_terms(e=None):
        from flet import context

        context.page.show_dialog(
            ft.AlertDialog(
                title=ft.Text(LBL_USAGE_AGREEMENT_TITLE, weight=ft.FontWeight.BOLD),
                content=ft.Container(
                    content=ft.Text(TERMS_TEXT, size=12, selectable=True),
                    width=420,
                ),
                actions=[
                    ft.TextButton(
                        LBL_CLOSE, on_click=lambda e: context.page.pop_dialog()
                    )
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
        )

    # -- build sections --

    # 1. Appearance
    appearance = _section_card(
        "Appearance",
        ft.Icons.PALETTE,
        [
            _setting_row(
                leading=ft.Icon(ft.Icons.DARK_MODE, size=18, color=AppColors.PRIMARY),
                title=LBL_DARK_MODE,
                subtitle=LBL_DARK_MODE_DESC,
                trailing=ft.Switch(
                    value=_is_dark(), on_change=_toggle_theme, autofocus=True
                ),
            ),
        ],
    )

    # 2. Localization
    countries = channel_provider.get_countries()
    country_names = [c.get("name", "") for c in countries if c.get("name")]
    if "Other" not in country_names:
        country_names.append("Other")
    current = state.user_country
    default_country = (
        current
        if current in country_names
        else (country_names[0] if country_names else None)
    )

    country_dialog = ft.AlertDialog(
        title=ft.Text("Select Country", size=16, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE
                                if c == default_country
                                else ft.Icons.RADIO_BUTTON_UNCHECKED,
                                size=16,
                                color=AppColors.PRIMARY
                                if c == default_country
                                else AppColors.grey_dim(),
                            ),
                            ft.Text(c, size=13),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(8, 8, 8, 8),
                    border_radius=8,
                    ink=True,
                    on_click=lambda e, c=c: (
                        _on_country_select(c),
                        _close_country_dialog(),
                    ),
                )
                for c in country_names
            ],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions_alignment=ft.MainAxisAlignment.END,
    )

    def _open_country_dialog(e):
        from flet import context

        context.page.show_dialog(country_dialog)

    def _close_country_dialog():
        from flet import context

        context.page.pop_dialog()

    localization = _section_card(
        "Localization",
        ft.Icons.PUBLIC,
        [
            _setting_row(
                leading=ft.Icon(ft.Icons.PUBLIC, color=AppColors.PRIMARY),
                title=LBL_DEFAULT_REGION,
                subtitle=LBL_FILTER_BY_COUNTRY,
                trailing=ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(default_country or "Select", size=13),
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16),
                        ],
                        spacing=4,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    width=150,
                    padding=ft.Padding(8, 6, 8, 6),
                    border=ft.Border.all(
                        1, ft.Colors.with_opacity(0.3, ft.Colors.OUTLINE_VARIANT)
                    ),
                    border_radius=8,
                    ink=True,
                    on_click=_open_country_dialog,
                ),
            ),
        ],
    )

    # 3. Data Management
    data_mgmt = _section_card(
        "Data Management",
        ft.Icons.STORAGE,
        [
            _setting_row(
                leading=ft.Icon(ft.Icons.HISTORY, size=18, color=AppColors.PRIMARY),
                title=LBL_CLEAR_HISTORY,
                subtitle=LBL_CLEAR_HISTORY_DESC,
                trailing=ft.OutlinedButton(
                    content=ft.Text(
                        LBL_CLEARING if is_clearing else LBL_CLEAR_HISTORY, size=12
                    ),
                    icon=ft.Icons.DELETE_OUTLINED,
                    disabled=is_clearing,
                    on_click=lambda e: asyncio.create_task(_clear_history()),
                ),
            ),
            _setting_row(
                leading=ft.Icon(ft.Icons.RESTART_ALT, size=18, color=AppColors.PRIMARY),
                title=LBL_RESET_LIBRARY,
                subtitle=LBL_RESET_LIBRARY_DESC,
                trailing=ft.OutlinedButton(
                    content=ft.Text(
                        LBL_RESETTING if is_resetting else LBL_RESET_LIBRARY, size=12
                    ),
                    icon=ft.Icons.RESTART_ALT,
                    disabled=is_resetting,
                    on_click=lambda e: asyncio.create_task(_reset_custom()),
                ),
            ),
        ],
    )

    # 4. Activity Terminal
    logs_count = len(MemoryLogHandler.get_logs())
    terminal = _section_card(
        "Development",
        ft.Icons.TERMINAL,
        [
            _setting_row(
                leading=ft.Icon(ft.Icons.TERMINAL, size=18, color=AppColors.PRIMARY),
                title=LBL_ACTIVITY_TERMINAL,
                subtitle=f"{logs_count} entries in memory",
                trailing=ft.OutlinedButton(
                    content=ft.Text(LBL_OPEN_TERMINAL, size=12),
                    icon=ft.Icons.TERMINAL,
                    on_click=_open_terminal,
                ),
            ),
        ],
    )

    # 5. About
    about = _section_card(
        "About",
        ft.Icons.INFO,
        [
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Image(
                            src="/icon.png",
                            width=56,
                            height=56,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=12,
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(APP_NAME, size=16, weight=ft.FontWeight.BOLD),
                                ft.Text(
                                    f"Version {APP_VERSION} · Flet {ft.__version__}",
                                    size=12,
                                    color=AppColors.grey_dim(),
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=14,
                ),
                padding=ft.Padding(4, 8, 4, 8),
            ),
            ft.Divider(height=1, color=AppColors.get_border_color(ft.context.page)),
            ft.TextButton(
                LBL_USAGE_AGREEMENT_BUTTON,
                icon=ft.Icons.GAVEL_ROUNDED,
                on_click=_show_terms,
            ),
        ],
    )

    return ft.ListView(
        controls=[appearance, localization, data_mgmt, terminal, about],
        expand=True,
        spacing=12,
        padding=ft.Padding(16, 16, 16, 24),
    )
