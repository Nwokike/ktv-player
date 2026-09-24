"""AppShell — top-level shell branching onboarding vs dashboard."""

import logging

import flet as ft
from flet import Control

from channels.provider import channel_provider
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


def _shell_view(page: ft.Page) -> ft.View | None:
    """The dashboard's own view.

    The app keeps a `/blank` view *beneath* the dashboard so Android's
    system back reaches Python instead of finishing the activity, and
    pushes `/play` views *above* it — so neither may be mistaken for the
    shell (a navigation bar attached to the player would render over the
    video).
    """
    if not page.views:
        return None
    for view in page.views:
        if view.route not in ("/blank", "/play"):
            return view
    return None


async def _onboarding_complete() -> None:
    """No-op default — completion handler is managed by AppController."""


@ft.component
def AppShell() -> Control:
    """Top-level shell. Reads observable state; renders Onboarding, Search, or dashboard."""
    selected_tab, set_selected_tab = ft.use_state(0)
    search_mode, set_search_mode = ft.use_state(None)
    controller = ft.use_context(ControllerMethodsCtx)

    controller.open_search = lambda mode="tv": set_search_mode(mode)

    def _go_home():
        # Back must also leave the search overlay — otherwise a back press
        # on Search (opened from Local) changes the hidden tab and appears
        # to do nothing.
        if search_mode is not None:
            set_search_mode(None)
        if selected_tab != 0:
            logger.info("Back → Home tab")
            set_selected_tab(0)

    controller.go_home = _go_home
    # Lets AppController decide what a back press means without reaching
    # into component state. Search counts as "not plain Home" so back
    # dismisses the overlay before it would consider leaving the app.
    controller.on_non_home_tab = lambda: selected_tab != 0 or search_mode is not None

    use_keyboard_shortcuts(
        controller=controller,
        on_search=lambda: set_search_mode("tv"),
        on_refresh=controller.refresh_channels,
    )

    state = ft.use_context(AppStateCtx)

    from flet import context

    def _sync_navigation_bar():
        page = context.page
        if not page or not page.views:
            return
        view = _shell_view(page)
        if view is None:
            return
        if _should_show_onboarding(state):
            if view.navigation_bar is not None:
                view.navigation_bar = None
                try:
                    page.update()
                except Exception:
                    pass
            return

        def _on_tab_change(e):
            idx = e.control.selected_index
            logger.info("Navigated to tab '%s' (index %d)", _TAB_NAMES[idx], idx)
            if search_mode is not None:
                set_search_mode(None)
            set_selected_tab(idx)

        destinations = [
            ft.NavigationBarDestination(icon=icon, label=label)
            for icon, label in zip(_TAB_ICONS, _TAB_NAMES, strict=True)
        ]
        view.navigation_bar = ft.NavigationBar(
            destinations=destinations,
            selected_index=selected_tab,
            on_change=_on_tab_change,
        )
        try:
            page.update()
        except Exception:
            pass

    ft.use_effect(
        _sync_navigation_bar,
        [selected_tab, state.has_accepted_terms, state.is_first_launch, search_mode],
    )

    from utils.channels import build_favorites_set

    fav_dep = (
        tuple(state.favorites)
        if isinstance(state.favorites, (list, set, tuple))
        else state.favorites
    )
    # Hook order must not depend on which branch renders, so this sits
    # outside the search conditional even though only search uses it.
    fav_set = ft.use_memo(
        lambda: build_favorites_set(state) if search_mode is not None else set(),
        [state.channels_hash, fav_dep, search_mode is not None],
    )

    if _should_show_onboarding(state):
        screen = OnboardingScreen(
            countries=channel_provider.get_countries(),
            on_complete=_onboarding_complete,
            prober=controller.refresh_channels,
        )
    elif search_mode is not None:
        from screens.search_screen import SearchScreen
        from utils.favorites import toggle_favorite

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

    return ft.SafeArea(content=screen, expand=True)
