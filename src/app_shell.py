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
    """Build the dashboard body container (NavigationBar is owned by the
    _ShellNavigationBar component riding inside the tree)."""
    return ft.Container(content=body, expand=True)


def _dashboard_view(page) -> object | None:
    """The view holding the shell tree — NOT views[0].

    The /blank back underlay is INSERTED at index 0 (main.py
    _ensure_back_underlay + the two deep-link branches), which pushes the
    dashboard to views[1] or later; /play is appended above it. Skipping
    those two routes is what makes the lookup correct in every state.
    """
    for v in getattr(page, "views", None) or []:
        if getattr(v, "route", None) not in ("/blank", "/play"):
            return v
    return None


@ft.component
def _ShellNavigationBar(selected_tab: int, visible: bool, on_change) -> Control:
    """Owns the dashboard view's navigation_bar.

    Rendered inside the AppShell tree (which lives in the dashboard view's
    controls), so the view that holds THIS component is the right target —
    located by skipping the /blank underlay and /play overlay rather than
    assuming an index. Unmount clears a bar this component installed.
    """
    installed = ft.use_ref(None)

    def _sync():
        try:
            from flet import context as _ctx

            page = _ctx.page
        except Exception:
            logger.debug("Nav bar sync: no page bound", exc_info=True)
            return
        try:
            root = _dashboard_view(page)
            if root is None:
                return
            if visible:
                destinations = [
                    ft.NavigationBarDestination(icon=icon, label=label)
                    for icon, label in zip(_TAB_ICONS, _TAB_NAMES, strict=True)
                ]
                root.navigation_bar = ft.NavigationBar(
                    destinations=destinations,
                    selected_index=selected_tab,
                    on_change=on_change,
                )
            else:
                root.navigation_bar = None
            installed.current = root
            page.update()
        except Exception:
            logger.debug("Nav bar sync failed", exc_info=True)

    def _cleanup():
        if installed.current is None:
            return
        installed.current = None
        try:
            from flet import context as _ctx

            page = _ctx.page
            root = _dashboard_view(page)
            if root is not None:
                root.navigation_bar = None
                page.update()
        except Exception:
            pass

    ft.use_effect(_sync, [selected_tab, visible])
    # NOTE: cleanup is the 3rd use_effect arg (not a setup return).
    ft.use_effect(lambda: None, [], _cleanup)
    return ft.Container(height=0, visible=False)


async def _onboarding_complete() -> None:
    """No-op default — completion handler is managed by AppController."""


@ft.component
def AppShell() -> Control:
    """Top-level shell. Reads observable state; renders Onboarding, Search, or dashboard."""
    selected_tab, set_selected_tab = ft.use_state(0)
    search_mode, set_search_mode = ft.use_state(None)
    # MUTATE the provided instance, don't copy: AppController hands its own
    # object to the context (main.py builds `methods` once, stores it as
    # self._controller_methods, and _handle_shell_back reads go_home /
    # on_non_home_tab from THAT object). A dataclasses.replace copy left the
    # controller holding defaults, so Back on a non-Home tab EXITED the app
    # instead of returning Home.
    controller = ft.use_context(ControllerMethodsCtx)

    def _go_home():
        # Back must also leave the search overlay — otherwise a back press
        # on Search (opened from Local) changes the hidden tab and appears
        # to do nothing.
        if search_mode is not None:
            set_search_mode(None)
        if selected_tab != 0:
            logger.info("Back → Home tab")
            set_selected_tab(0)

    # Lets AppController decide what a back press means without reaching
    # into component state. Search counts as "not plain Home" so back
    # dismisses the overlay before it would consider leaving the app.
    def _open_search(mode: str = "tv"):
        set_search_mode(mode)

    def _on_non_home_tab() -> bool:
        return selected_tab != 0 or search_mode is not None

    if callable(getattr(controller, "go_home", None)):
        controller.go_home = _go_home
        controller.open_search = _open_search
        controller.on_non_home_tab = _on_non_home_tab

    use_keyboard_shortcuts(
        controller=controller,
        on_search=lambda: set_search_mode("tv"),
        on_refresh=controller.refresh_channels,
    )

    state = ft.use_context(AppStateCtx)

    def _on_tab_change(e):
        idx = e.control.selected_index
        if not isinstance(idx, int) or not 0 <= idx < len(_TAB_NAMES):
            logger.warning("Ignoring out-of-range tab index: %r", idx)
            return
        logger.info("Navigated to tab '%s' (index %d)", _TAB_NAMES[idx], idx)
        if search_mode is not None:
            set_search_mode(None)
        set_selected_tab(idx)

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

        def _on_play(url: str, title: str | None = None):
            try:
                from flet import context as _ctx

                _ctx.page.run_task(controller.play_stream, url, title)
            except Exception:
                logger.exception("Search play failed for %s", url)

        def _on_toggle_fav(url: str):
            toggle_favorite(url, state)

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
        # The nav bar owner rides along inside the tree (zero-size): it syncs
        # views[0].navigation_bar from state deps — page.render() takes controls,
        # not a View, so the bar can't be returned as part of the tree itself.
        screen = ft.Column(
            controls=[
                _dashboard_scaffold(body=tab_body),
                _ShellNavigationBar(
                    selected_tab=selected_tab,
                    visible=True,
                    on_change=_on_tab_change,
                ),
            ],
            expand=True,
            spacing=0,
        )

    return ft.SafeArea(content=screen, expand=True)
