"""AppShell — top-level shell branching onboarding vs dashboard."""

import logging

import flet as ft
from flet import Control

from channels.provider import channel_provider
from hooks.use_focus_scope import FocusScope
from hooks.use_keyboard_shortcuts import use_keyboard_shortcuts
from screens.home_screen import HomeScreen
from screens.local_screen import LocalScreen
from screens.onboarding_screen import OnboardingScreen
from screens.settings_screen import SettingsScreen
from state.app_state import AppStateCtx
from state.controller_ctx import ControllerMethodsCtx

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
    """Top-level shell. Reads observable state; renders Onboarding, Search, or dashboard."""
    selected_tab, set_selected_tab = ft.use_state(0)
    search_mode, set_search_mode = ft.use_state(None)
    controller = ft.use_context(ControllerMethodsCtx)

    controller.open_search = lambda mode="tv": set_search_mode(mode)

    use_keyboard_shortcuts(
        controller=controller,
        on_search=lambda: set_search_mode("tv"),
        on_refresh=controller.refresh_channels,
    )

    state = ft.use_context(AppStateCtx)

    if _should_show_onboarding(state):
        screen = OnboardingScreen(
            countries=channel_provider.get_countries(),
            on_complete=_onboarding_complete,
            prober=controller.refresh_channels,
        )
    elif search_mode is not None:
        from screens.search_screen import SearchScreen
        from utils.channels import build_favorites_set
        from utils.favorites import toggle_favorite

        fav_dep = (
            tuple(state.favorites)
            if isinstance(state.favorites, (list, set, tuple))
            else state.favorites
        )
        fav_set = ft.use_memo(
            lambda: build_favorites_set(state), [state.channels_hash, fav_dep]
        )

        def _on_play(url: str):
            import asyncio

            asyncio.create_task(controller.play_stream(url, None))

        def _on_toggle_fav(url: str):
            toggle_favorite(state, url)

        screen = SearchScreen(
            initial_mode=search_mode,
            channels=state.channels,
            favorites_set=fav_set,
            on_play=_on_play,
            on_toggle_favorite=_on_toggle_fav,
            on_back=lambda: set_search_mode(None),
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

        def _sync_navigation_bar():
            if page and page.views:

                def _on_tab_change(e):
                    idx = e.control.selected_index
                    logger.info(
                        "Navigated to tab '%s' (index %d)", _TAB_NAMES[idx], idx
                    )
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
                page.update()

        ft.use_effect(_sync_navigation_bar, [selected_tab])

    return ft.SafeArea(content=screen, expand=True)
