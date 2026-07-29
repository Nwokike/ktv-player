"""SettingsScreen — modern, compact Material 3 grouped settings interface.

Single-line compact setting rows with right-aligned controls, clean text hierarchy,
and zero unnecessary vertical wrapping.
"""

import asyncio
import logging

import flet as ft
from flet.controls.control import Control

from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from app_next.utils.notifications import notify, notify_warning
from app_next.utils.theme_utils import toggle_theme as _toggle_theme_util
from channels.provider import channel_provider
from core.constants import (
    APP_NAME,
    APP_VERSION,
    LBL_ABOUT,
    LBL_ACTIVITY_TERMINAL,
    LBL_APPEARANCE,
    LBL_CLEAR_HISTORY,
    LBL_CLEAR_HISTORY_DESC,
    LBL_COUNTRY_UPDATED,
    LBL_DARK_MODE,
    LBL_DARK_MODE_DESC,
    LBL_DATA_MANAGEMENT,
    LBL_DEFAULT_REGION,
    LBL_HISTORY_CLEARED,
    LBL_LIBRARY_RESET,
    LBL_LIVE_ACTIVITY_TERMINAL,
    LBL_LOCALIZATION,
    LBL_OPEN_TERMINAL,
    LBL_RESET_LIBRARY,
    LBL_RESET_LIBRARY_DESC,
    LBL_TERMINAL_DESC,
    TERMS_TEXT,
)
from core.logger_handler import MemoryLogHandler
from core.state import state as core_state
from core.theme import AppColors
from core.tokens import (
    BORDER_RADIUS_LG,
    BORDER_RADIUS_MD,
    BORDER_RADIUS_XL,
    DIALOG_HEIGHT_MD,
    DIALOG_WIDTH_MD,
    FONT_FAMILY_MONO,
    FONT_LG,
    FONT_MD,
    FONT_SM,
    FONT_XS,
    ICON_MD,
    ICON_SM,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XS,
)
from database.manager import db_manager

_notify = notify
_notify_warning = notify_warning
logger = logging.getLogger("SettingsScreen")

_SECTIONS = [
    {"key": "appearance", "icon": ft.Icons.PALETTE, "title": LBL_APPEARANCE},
    {"key": "localization", "icon": ft.Icons.PUBLIC, "title": LBL_LOCALIZATION},
    {
        "key": "data_management",
        "icon": ft.Icons.STORAGE,
        "title": LBL_DATA_MANAGEMENT,
    },
    {
        "key": "custom_content",
        "icon": ft.Icons.TERMINAL,
        "title": LBL_ACTIVITY_TERMINAL,
    },
    {"key": "about", "icon": ft.Icons.INFO, "title": LBL_ABOUT},
]


def build_logs_dialog(page: ft.Page) -> ft.AlertDialog:
    """Build live activity terminal modal dialog."""
    logs = MemoryLogHandler.get_logs()
    logs_str = "\n".join(logs) if logs else "No activity recorded yet."

    log_text_control = ft.Text(
        value=logs_str,
        font_family=FONT_FAMILY_MONO,
        size=FONT_SM,
        color=AppColors.TERMINAL_TEXT,
        selectable=True,
    )

    async def _copy_logs(e=None):
        try:
            await ft.Clipboard().set(log_text_control.value)
            snack = ft.SnackBar(content=ft.Text("Activity log copied to clipboard!"))
            page.overlay.append(snack)
            snack.open = True
            page.update()
        except Exception:
            pass

    def _clear_logs(e=None):
        MemoryLogHandler.clear_logs()
        log_text_control.value = "Activity log cleared."
        page.update()

    return ft.AlertDialog(
        title=ft.Row(
            controls=[
                ft.Icon(ft.Icons.TERMINAL, color=AppColors.PRIMARY, size=ICON_MD),
                ft.Text(
                    LBL_LIVE_ACTIVITY_TERMINAL,
                    weight=ft.FontWeight.BOLD,
                    size=FONT_LG,
                ),
                ft.Container(
                    content=ft.Text(
                        f"{len(logs)} logs", size=FONT_XS, color=ft.Colors.WHITE
                    ),
                    bgcolor=AppColors.PRIMARY,
                    border_radius=BORDER_RADIUS_LG,
                    padding=ft.Padding(SPACING_SM, SPACING_XS, SPACING_SM, SPACING_XS),
                ),
            ],
            spacing=SPACING_SM,
        ),
        content=ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(
                        LBL_TERMINAL_DESC,
                        size=FONT_SM,
                        color=AppColors.grey_dim(),
                    ),
                    ft.Container(
                        content=ft.Column(
                            controls=[log_text_control],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        bgcolor=AppColors.TERMINAL_BG,
                        border=ft.Border.all(
                            1, ft.Colors.with_opacity(0.25, ft.Colors.WHITE)
                        ),
                        border_radius=BORDER_RADIUS_MD,
                        padding=SPACING_MD,
                        expand=True,
                    ),
                ],
                spacing=SPACING_SM,
            ),
            width=DIALOG_WIDTH_MD,
            height=DIALOG_HEIGHT_MD,
        ),
        actions=[
            ft.TextButton(
                "Copy to Clipboard",
                icon=ft.Icons.COPY,
                on_click=lambda e: asyncio.create_task(_copy_logs()),
            ),
            ft.TextButton(
                "Clear",
                icon=ft.Icons.DELETE_SWEEP,
                on_click=_clear_logs,
            ),
            ft.TextButton(
                "Close",
                on_click=lambda e: page.pop_dialog(),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )


@ft.component
def SettingsScreen() -> Control:
    logger.info("Building compact SettingsScreen view")
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    is_clearing, set_is_clearing = ft.use_state(False)
    is_resetting, set_is_resetting = ft.use_state(False)

    async def _clear_history():
        logger.info("Clearing watch history...")
        set_is_clearing(True)
        try:
            await db_manager.clear_history()
            core_state.history.clear()
            _notify(LBL_HISTORY_CLEARED)
            logger.info("Watch history cleared successfully")
        except Exception as ex:
            logger.error("Failed to clear history: %s", ex)
            _notify_warning("Failed to clear history.")
        finally:
            set_is_clearing(False)

    async def _reset_custom():
        logger.info("Resetting custom content library...")
        set_is_resetting(True)
        try:
            await db_manager.clear_custom_content()
            _notify(LBL_LIBRARY_RESET)
            await controller.refresh_channels()
            logger.info("Custom library reset successfully")
        except Exception as ex:
            logger.error("Failed to reset custom content: %s", ex)
            _notify_warning("Failed to reset custom content.")
        finally:
            set_is_resetting(False)

    def _update_country(country_name: str):
        logger.info("Updating user region focus to %s", country_name)

        async def _do():
            await db_manager.set_setting("user_country", country_name)
            core_state.user_country = country_name
            _notify(LBL_COUNTRY_UPDATED.format(country=country_name))

        asyncio.create_task(_do())

    def _is_dark() -> bool:
        from flet.controls.context import context

        return AppColors._is_dark(context.page)

    def _toggle_theme(e):
        from flet.controls.context import context

        logger.info("Theme mode toggle triggered")
        _toggle_theme_util(context.page)

    def _open_terminal(e):
        from flet.controls.context import context

        logger.info("Opening Live Activity Terminal dialog")
        context.page.show_dialog(build_logs_dialog(context.page))

    def _show_terms_dialog(e=None):
        from flet.controls.context import context

        dlg = ft.AlertDialog(
            title=ft.Text("Usage Agreement & Legal", weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Text(TERMS_TEXT, size=FONT_SM, selectable=True),
                width=450,
            ),
            actions=[
                ft.TextButton("Close", on_click=lambda e: context.page.pop_dialog())
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        context.page.show_dialog(dlg)

    def _build_card(title: str, icon: str, content: Control) -> Control:
        from flet.controls.context import context

        page = context.page
        card_bg = AppColors.get_card_bg(page)
        border_color = AppColors.get_border_color(page)

        return ft.Container(
            bgcolor=card_bg,
            border=ft.Border.all(1, border_color),
            border_radius=BORDER_RADIUS_XL,
            padding=ft.Padding(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(icon, color=AppColors.PRIMARY, size=ICON_MD),
                            ft.Text(
                                title,
                                size=FONT_MD,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                        spacing=SPACING_SM,
                    ),
                    ft.Divider(height=1, color=border_color),
                    content,
                ],
                spacing=SPACING_SM,
            ),
        )

    # --- Section content builders (Compact, Single-Line Layouts) ---

    def _appearance_content() -> Control:
        return ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.DARK_MODE, size=ICON_SM, color=AppColors.PRIMARY
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    LBL_DARK_MODE,
                                    size=FONT_MD,
                                    weight=ft.FontWeight.W_500,
                                ),
                                ft.Text(
                                    LBL_DARK_MODE_DESC,
                                    size=FONT_SM,
                                    color=AppColors.grey_dim(),
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=SPACING_SM,
                ),
                ft.Switch(value=_is_dark(), on_change=_toggle_theme, autofocus=True),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _localization_content() -> Control:
        countries = channel_provider.get_countries()
        country_names = [c.get("name", "") for c in countries if c.get("name")]
        if "Other" not in country_names:
            country_names.append("Other")

        current = state.user_country
        default_val = (
            current
            if current in country_names
            else (country_names[0] if country_names else None)
        )

        def _on_dropdown_select(e):
            if e.control.value:
                _update_country(e.control.value)

        return ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.PUBLIC, size=ICON_SM, color=AppColors.PRIMARY),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    LBL_DEFAULT_REGION,
                                    size=FONT_MD,
                                    weight=ft.FontWeight.W_500,
                                ),
                                ft.Text(
                                    "Filter default channels by country",
                                    size=FONT_SM,
                                    color=AppColors.grey_dim(),
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=SPACING_SM,
                ),
                ft.Container(
                    content=ft.Dropdown(
                        value=default_val,
                        options=[
                            ft.DropdownOption(key=c, text=c) for c in country_names
                        ],
                        on_select=_on_dropdown_select,
                        text_size=FONT_SM,
                        content_padding=ft.Padding(10, 4, 10, 4),
                        dense=True,
                        border_radius=BORDER_RADIUS_MD,
                    ),
                    width=160,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _data_content() -> Control:
        from flet.controls.context import context

        border_color = AppColors.get_border_color(context.page)
        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.HISTORY,
                                    size=ICON_SM,
                                    color=AppColors.PRIMARY,
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            LBL_CLEAR_HISTORY,
                                            size=FONT_MD,
                                            weight=ft.FontWeight.W_500,
                                        ),
                                        ft.Text(
                                            LBL_CLEAR_HISTORY_DESC,
                                            size=FONT_SM,
                                            color=AppColors.grey_dim(),
                                        ),
                                    ],
                                    spacing=2,
                                ),
                            ],
                            spacing=SPACING_SM,
                        ),
                        ft.OutlinedButton(
                            content=ft.Text(
                                "Clearing..." if is_clearing else LBL_CLEAR_HISTORY,
                                size=FONT_SM,
                            ),
                            icon=ft.Icons.DELETE_OUTLINED,
                            disabled=is_clearing,
                            on_click=lambda e: asyncio.create_task(_clear_history()),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Divider(height=1, color=border_color),
                ft.Row(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(
                                    ft.Icons.RESTART_ALT,
                                    size=ICON_SM,
                                    color=AppColors.PRIMARY,
                                ),
                                ft.Column(
                                    controls=[
                                        ft.Text(
                                            LBL_RESET_LIBRARY,
                                            size=FONT_MD,
                                            weight=ft.FontWeight.W_500,
                                        ),
                                        ft.Text(
                                            LBL_RESET_LIBRARY_DESC,
                                            size=FONT_SM,
                                            color=AppColors.grey_dim(),
                                        ),
                                    ],
                                    spacing=2,
                                ),
                            ],
                            spacing=SPACING_SM,
                        ),
                        ft.OutlinedButton(
                            content=ft.Text(
                                "Resetting..." if is_resetting else LBL_RESET_LIBRARY,
                                size=FONT_SM,
                            ),
                            icon=ft.Icons.RESTART_ALT,
                            disabled=is_resetting,
                            on_click=lambda e: asyncio.create_task(_reset_custom()),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
            ],
            spacing=SPACING_SM,
        )

    def _logs_content() -> Control:
        logs_count = len(MemoryLogHandler.get_logs())
        return ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.TERMINAL, size=ICON_SM, color=AppColors.PRIMARY
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    LBL_ACTIVITY_TERMINAL,
                                    size=FONT_MD,
                                    weight=ft.FontWeight.W_500,
                                ),
                                ft.Text(
                                    f"{logs_count} log entries recorded in memory",
                                    size=FONT_SM,
                                    color=AppColors.grey_dim(),
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=SPACING_SM,
                ),
                ft.FilledButton(
                    LBL_OPEN_TERMINAL,
                    icon=ft.Icons.TERMINAL,
                    on_click=_open_terminal,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _about_content() -> Control:
        from flet.controls.context import context

        border_color = AppColors.get_border_color(context.page)
        return ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Image(
                                src="/icon.png",
                                width=64,
                                height=64,
                                fit=ft.BoxFit.CONTAIN,
                                border_radius=BORDER_RADIUS_MD,
                            ),
                        ),
                        ft.Column(
                            controls=[
                                ft.Text(
                                    APP_NAME, size=FONT_LG, weight=ft.FontWeight.BOLD
                                ),
                                ft.Text(
                                    f"Version {APP_VERSION} (Engine: Flet {ft.__version__})",
                                    size=FONT_SM,
                                    color=AppColors.grey_dim(),
                                ),
                            ],
                            spacing=2,
                        ),
                    ],
                    spacing=SPACING_MD,
                ),
                ft.Divider(height=1, color=border_color),
                ft.Row(
                    controls=[
                        ft.TextButton(
                            "Usage Agreement & Legal Terms",
                            icon=ft.Icons.GAVEL_ROUNDED,
                            on_click=_show_terms_dialog,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
            ],
            spacing=SPACING_SM,
        )

    cards = [
        _build_card(LBL_APPEARANCE, ft.Icons.PALETTE, _appearance_content()),
        _build_card(LBL_LOCALIZATION, ft.Icons.PUBLIC, _localization_content()),
        _build_card(LBL_DATA_MANAGEMENT, ft.Icons.STORAGE, _data_content()),
        _build_card(LBL_ACTIVITY_TERMINAL, ft.Icons.TERMINAL, _logs_content()),
        _build_card(LBL_ABOUT, ft.Icons.INFO, _about_content()),
    ]

    return ft.ListView(
        controls=cards,
        expand=True,
        spacing=SPACING_MD,
        padding=ft.Padding(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_LG),
    )
