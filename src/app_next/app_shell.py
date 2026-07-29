"""AppShell — top-level @ft.component rendered via page.render(AppShell).

Branches between OnboardingScreen and the dashboard scaffold based on the
observable AppState. Owns NavigationBar selected-index as use_state. Wraps
the whole tree in FocusScope so the Android TV / Fire Stick Back key pops
the view stack via ControllerMethodsCtx.pop_views.

OBSERVABLE SUBSCRIPTION NOTE: state is accessed via use_context, NOT a
plain import. use_context auto-attaches an ObservableSubscription when
the resolved value is an Observable (verified in
.venv/lib/python3.13/site-packages/flet/components/hooks/use_context.py
lines 105-106). Without this, flipping state.has_accepted_terms inside
OnboardingScreen's submit handler would NOT cause AppShell to re-render
from the Onboarding branch to the dashboard branch.
"""

import flet as ft
from flet.controls.control import Control

from app_next.hooks.use_focus_scope import FocusScope
from app_next.hooks.use_keyboard_shortcuts import use_keyboard_shortcuts
from app_next.screens.home_screen import HomeScreen
from app_next.screens.local_screen import LocalScreen
from app_next.screens.onboarding_screen import OnboardingScreen
from app_next.screens.placeholder_screen import PlaceholderScreen
from app_next.screens.search_screen import SearchScreen
from app_next.screens.settings_screen import SettingsScreen
from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from channels.provider import channel_provider

_TAB_NAMES = ("Home", "Search", "Local", "Settings")
_TAB_ICONS = (
    ft.Icons.HOME,
    ft.Icons.SEARCH,
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
    """No-op default — the real completion handler lives on AppController.

    Onboarding writes `accepted_terms=true` to DB + flips observable state;
    once `state.has_accepted_terms` becomes True the shell re-renders to the
    dashboard on its own (no explicit navigation). Nothing to do here.
    """


@ft.component
def AppShell() -> Control:
    """Top-level shell. Reads observable state; renders Onboarding or dashboard."""
    selected_tab, set_selected_tab = ft.use_state(0)
    controller = ft.use_context(ControllerMethodsCtx)

    use_keyboard_shortcuts(
        controller=controller,
        on_search=lambda: set_selected_tab(1),
        on_refresh=controller.refresh_channels,
    )

    # State is accessed via use_context (auto-subscribes to observable changes).
    state = ft.use_context(AppStateCtx)

    if _should_show_onboarding(state):
        # Onboarding is the first screen — no back-navigation needed.
        # Return the screen DIRECTLY (not wrapped in FocusScope) so the
        # inner ListView receives bounded height constraints from the View
        # and creates a proper scroll viewport. FocusScope/KeyboardListener
        # does NOT have host_expanded=True, so expand=True on any child of
        # KeyboardListener is a no-op — the ListView never gets bounded
        # height and cannot scroll (verified in Flet 0.86.4).
        return OnboardingScreen(
            countries=channel_provider.get_countries(),
            on_complete=_onboarding_complete,
            prober=controller.refresh_channels,
        )
    else:
        if _TAB_NAMES[selected_tab] == "Home":
            tab_body = HomeScreen(key=ft.ValueKey("home"))
        elif _TAB_NAMES[selected_tab] == "Search":
            tab_body = SearchScreen(key=ft.ValueKey("search"))
        elif _TAB_NAMES[selected_tab] == "Local":
            tab_body = LocalScreen(key=ft.ValueKey("local"))
        elif _TAB_NAMES[selected_tab] == "Settings":
            tab_body = SettingsScreen(key=ft.ValueKey("settings"))
        else:
            tab_body = PlaceholderScreen(
                key=ft.ValueKey(_TAB_NAMES[selected_tab]),
                name=_TAB_NAMES[selected_tab],
            )
        screen = _dashboard_scaffold(body=tab_body)

        # Set NavigationBar on the root View so Flutter's Scaffold pins it to the bottom
        from flet.controls.context import context

        page = context.page
        destinations = [
            ft.NavigationBarDestination(icon=icon, label=label)
            for icon, label in zip(_TAB_ICONS, _TAB_NAMES, strict=True)
        ]
        page.views[0].navigation_bar = ft.NavigationBar(
            destinations=destinations,
            selected_index=selected_tab,
            on_change=lambda e: set_selected_tab(e.control.selected_index),
        )

    async def _on_back(e):
        controller.pop_views()

    return FocusScope(child=screen, on_back=_on_back)
