"""AppShell — top-level shell branching onboarding vs dashboard."""

import logging

import flet as ft
from flet import Control

from app_next.hooks.use_focus_scope import FocusScope
from app_next.hooks.use_keyboard_shortcuts import use_keyboard_shortcuts
from app_next.screens.home_screen import HomeScreen
from app_next.screens.local_screen import LocalScreen
from app_next.screens.onboarding_screen import OnboardingScreen
from app_next.screens.settings_screen import SettingsScreen
from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from channels.provider import channel_provider

logger = logging.getLogger("AppShell")

_TAB_NAMES = ("Home", "Local", "Settings")
_TAB_ICONS = (
    ft.Icons.HOME,
    ft.Icons.FOLDER,
    ft.Icons.SETTINGS,
)


def _should_show_onboarding(state) -> bool:
    """Mirror of the branch in AppShell — exported for tests."""
    return state.is_first_launch or not state.has_accepted_terms


def _dashboard_scaffold(body: Control) -> Control:
    """Build the dashboard body container (NavigationBar is set on the View)."""
    return ft.Container(content=body, expand=True)


async def _onboarding_complete() -> None:
    """No-op default — completion handler is managed by AppController."""


@ft.component
def AppShell() -> Control:
    """Top-level shell. Reads observable state; renders Onboarding or dashboard."""
    selected_tab, set_selected_tab = ft.use_state(0)
    controller = ft.use_context(ControllerMethodsCtx)

    use_keyboard_shortcuts(
        controller=controller,
        on_search=lambda: set_selected_tab(0),
        on_refresh=controller.refresh_channels,
    )

    state = ft.use_context(AppStateCtx)

    if _should_show_onboarding(state):
        screen = OnboardingScreen(
            countries=channel_provider.get_countries(),
            on_complete=_onboarding_complete,
            prober=controller.refresh_channels,
        )
    else:
        if _TAB_NAMES[selected_tab] == "Local":
            tab_body = LocalScreen(key=ft.ValueKey("local"))
        elif _TAB_NAMES[selected_tab] == "Settings":
            tab_body = SettingsScreen(key=ft.ValueKey("settings"))
        else:
            tab_body = HomeScreen(key=ft.ValueKey("home"))
        screen = _dashboard_scaffold(body=tab_body)

        from flet import context

        page = context.page

        def _on_tab_change(e):
            idx = e.control.selected_index
            logger.info("Navigated to tab '%s' (index %d)", _TAB_NAMES[idx], idx)
            set_selected_tab(idx)

        destinations = [
            ft.NavigationBarDestination(icon=icon, label=label)
            for icon, label in zip(_TAB_ICONS, _TAB_NAMES, strict=True)
        ]
        page.views[0].navigation_bar = ft.NavigationBar(
            destinations=destinations,
            selected_index=selected_tab,
            on_change=_on_tab_change,
        )

    async def _on_back(e):
        controller.pop_views()

    return FocusScope(child=ft.SafeArea(content=screen, expand=True), on_back=_on_back)
