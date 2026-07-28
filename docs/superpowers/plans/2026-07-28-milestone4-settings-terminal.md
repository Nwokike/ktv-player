# Milestone 4 — Settings Screen + Activity Terminal Logs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. **The main agent must verify every code change before commit.**

**Goal:** Replace the legacy `preferences_tab.py` (283 lines) + `preferences_logs.py` (79 lines) with a single `@ft.component`-based `SettingsScreen`. After this milestone the app's four navigation destinations are all real: Home (M2), Search (M3), Local (M3), Settings (M4).

**Architecture:** A vertical `ListView(build_controls_on_demand=True)` of M3-style `SectionList` rows. Each section is a `ListTile(focusable=True)` with leading icon, title, subtitle, and a trailing action (switch, button, or disclosure chevron). The terminal logs dialog is a separate `@ft.component ActivityTerminalDialog` that wraps the existing `MemoryLogHandler.get_logs()` in a dark-background `ListView(auto_scroll=True)` — matching the legacy Appearance but using our clean component model.

**Files for this milestone:** 2 source + 2 test + 1 AppShell edit.

---

## Task 1: `SettingsScreen` component

- [ ] **Write failing tests** → implement → commit

**Tests** (`tests/app_next/test_settings_screen.py`):

```python
from app_next.screens.settings_screen import SettingsScreen
from app_next.screens.settings_screen import _SECTIONS, _section_for_key


def test_settings_screen_marked_as_component():
    assert getattr(SettingsScreen, "__is_component__", False) is True


def test_sections_cover_expected_keys():
    keys = {s["key"] for s in _SECTIONS}
    expected = {
        "appearance",
        "localization",
        "data_management",
        "custom_content",
        "about",
    }
    assert keys == expected


def test_section_for_key_found():
    s = _section_for_key("appearance")
    assert s is not None
    assert s["title"] != ""
```

**Implementation** (`src/app_next/screens/settings_screen.py`):

```python
"""SettingsScreen — appearance, localization, data management, about."""

import asyncio
import flet as ft
from flet.controls.control import Control

from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from app_next.hooks.use_storage import use_storage
from app_next.components.empty_state import EmptyState
from core.constants import (
    LBL_LOCALIZATION,
    LBL_LOCALIZATION_DESC,
    LBL_DATA_MANAGEMENT,
    LBL_CLEAR_HISTORY,
    LBL_CLEAR_HISTORY_DESC,
    LBL_HISTORY_CLEARED,
    LBL_RESET_LIBRARY,
    LBL_RESET_LIBRARY_DESC,
    LBL_LIBRARY_RESET,
    LBL_COUNTRY_UPDATED,
)
from core.logger_handler import MemoryLogHandler
from core.state import state as core_state
from core.theme import AppColors
from database.manager import db_manager
from channels.provider import channel_provider

_SECTIONS = [
    {"key": "appearance", "icon": ft.Icons.PALETTE, "title": "Appearance"},
    {"key": "localization", "icon": ft.Icons.PUBLIC, "title": "Localization"},
    {"key": "data_management", "icon": ft.Icons.STORAGE, "title": "Data Management"},
    {"key": "custom_content", "icon": ft.Icons.PLAYLIST_ADD, "title": "Custom Content"},
    {"key": "about", "icon": ft.Icons.INFO, "title": "About"},
]


def _section_for_key(key: str) -> dict | None:
    return next((s for s in _SECTIONS if s["key"] == key), None)


@ft.component
def SettingsScreen() -> Control:
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)
    storage = use_storage()

    async def _clear_history():
        try:
            await db_manager.clear_history()
            core_state.history.clear()
            _notify(LBL_HISTORY_CLEARED)
        except Exception:
            _notify("Failed to clear history.")

    async def _reset_custom():
        try:
            await db_manager.clear_custom_content()
            _notify(LBL_LIBRARY_RESET)
            await controller.refresh_channels()
        except Exception:
            _notify("Failed to reset custom content.")

    async def _open_logs(e):
        from app_next.screens.settings_screen import (
            ActivityTerminalDialog,
        )  # local avoids circular

        dlg = ActivityTerminalDialog(on_close=lambda: page.pop_dialog())
        context.page.show_dialog(dlg)

    def _update_country(country_name: str):
        async def _do():
            await db_manager.set_setting("user_country", country_name)
            core_state.user_country = country_name
            _notify(LBL_COUNTRY_UPDATED.format(country=country_name))

        asyncio.create_task(_do())

    def _toggle_theme(e):
        page = context.page
        new_mode = (
            ft.ThemeMode.LIGHT
            if page.theme_mode == ft.ThemeMode.DARK
            else ft.ThemeMode.DARK
        )
        page.theme_mode = new_mode

        async def save():
            await db_manager.set_setting(
                "theme_mode", "dark" if new_mode == ft.ThemeMode.DARK else "light"
            )

        asyncio.create_task(save())

    tiles = []
    for section in _SECTIONS:
        tiles.append(
            ft.ListTile(
                leading=ft.Icon(section["icon"]),
                title=ft.Text(section["title"]),
                on_click=lambda e, k=section["key"]: _section_action(
                    k,
                    _clear_history,
                    _reset_custom,
                    _open_logs,
                    _update_country,
                    state,
                    controller,
                ),
                focusable=True,
            )
        )
        tiles.append(ft.Divider(height=1))

    return ft.ListView(controls=tiles, expand=True, spacing=4, padding=10)
``` 

(Keep the helper functions `_section_action`, `_notify`, and `ActivityTerminalDialog` in the same file. The `_section_action` dispatches: appearance → no sub-action (theme toggle is the page-level switch); localization → open country picker dialog; data_management → show two-option action sheet; custom_content → show logs + reset options; about → show app info dialog.)

**Commit:**

```bash
git add src/app_next/screens/settings_screen.py tests/app_next/test_settings_screen.py
git commit -m "feat(app_next.screens): SettingsScreen with section list + actions"
```

---

## Task 2: `ActivityTerminalDialog` component

- [ ] **Implement** inside `settings_screen.py` (single file). No separate test file needed — the terminal dialog is a dependency of SettingsScreen and tested through manual smoke.

```python
@ft.component
def ActivityTerminalDialog(on_close) -> ft.AlertDialog:
    logs = MemoryLogHandler.get_logs()
    log_text = "\n".join(logs) if logs else "No activity logs recorded yet."

    log_text_control = ft.Text(
        value=log_text,
        size=11,
        font_family="monospace",
        color=AppColors.SUCCESS,
        selectable=True,
    )

    async def _copy(e):
        try:
            await ft.Clipboard().set_async(log_text_control.value)
        except Exception:
            pass

    return ft.AlertDialog(
        modal=True,
        title=ft.Text("Activity Terminal"),
        content=ft.Container(
            content=ft.ListView(
                controls=[log_text_control],
                auto_scroll=True,
                auto_scroll_animation=0,
            ),
            bgcolor=ft.Colors.BLACK87,
            border_radius=8,
            padding=8,
            width=450,
            height=480,
        ),
        actions=[
            ft.TextButton("Copy", on_click=_copy),
            ft.TextButton("Close", on_click=lambda e: on_close()),
        ],
    )
```

(Verified: `MemoryLogHandler.get_logs()` returns `list[str]` — synchronous, no IO. `ft.Clipboard().set_async` attempted — if not available, use `ft.Clipboard().set()` which is sync in this version.)

---

## Task 3: Wire into AppShell + manual smoke

Modify `app_shell.py` to replace tab 3 (index 3) with `SettingsScreen`:

```python
elif _TAB_NAMES[selected_tab] == "Settings":
    from app_next.screens.settings_screen import SettingsScreen
    body = SettingsScreen(key=ft.ValueKey("settings"))
```

Manual smoke:
1. Settings tab shows 5 sections: Appearance, Localization, Data Management, Custom Content, About.
2. Tapping "Appearance" does nothing (theme toggle is on the Home header; kept in sync via observable state).
3. Tapping "Localization" opens a country-picker dialog; select → persists to DB.
4. Tapping "Data Management" shows Clear History and Reset Library buttons; each triggers a confirmation + notification.
5. Tapping "Activity Terminal" opens the dark log viewer with server logs; "Copy" copies to clipboard.
6. "About" shows version + framework info.

**Commit:**

```bash
git add src/app_next/app_shell.py
git commit -m "feat(app_next): wire SettingsScreen into AppShell tab 3"
```