"""KTV Player — main entry point and AppController."""

import asyncio
import contextlib
import logging
import os
import urllib.parse

import flet as ft

import core.logger_handler  # noqa: F401
from components.player.immersive_player import ImmersivePlayer
from core.constants import (
    APP_NAME,
    CDN_HEADER_OVERRIDES,
    ERR_NETWORK,
)
from core.logging_config import setup_logging
from core.state import state
from core.theme import AppTheme
from database.manager import db_manager
from hooks.use_focus_scope import FocusScope
from services.ad_service import AdService
from services.liveliness_checker import LivelinessChecker

logger = logging.getLogger(__name__)

from core.url_validator import _is_valid_play_url


class AppController:
    def __init__(self, page: ft.Page):
        self.page = page
        self.ad_service: AdService | None = None
        self.liveliness: LivelinessChecker | None = None
        self._loading_lock: asyncio.Lock | None = None
        self._is_player_closing: bool = False
        # Explicit modal name stack so _handle_back can pop the
        # topmost dialog before popping a view.
        self._modal_stack: list[str] = []

    async def init(self):
        import sys

        from core.constants import APP_VERSION

        logger.info(
            "Starting %s v%s on Python %s (Flet %s)",
            APP_NAME,
            APP_VERSION,
            sys.version.split()[0],
            ft.__version__,
        )

        self.page.title = APP_NAME
        self.page.padding = 0
        self.page.spacing = 0

        self.page.fonts = {"Outfit": "assets/outfit.css"}
        self.page.theme = AppTheme.get_light_theme()
        self.page.dark_theme = AppTheme.get_dark_theme()
        self.page.theme.font_family = "Outfit"
        self.page.dark_theme.font_family = "Outfit"
        self.page.theme_mode = ft.ThemeMode.SYSTEM

        self.page.on_error = self._on_global_error

        # Register a singleton FilePicker at boot. FilePicker extends
        # Service (verified .venv/controls/services/file_picker.py:166-167
        # + service.py:11-19) and self-registers through page._services.
        # Constructing it inline per-call loses the registration on
        # Android — pages.services.append(picker) then assigns the
        # reference so local_screen can call page.file_picker directly.
        file_picker = ft.FilePicker()
        self.page.services.append(file_picker)
        self.page.file_picker = file_picker

        # Init services
        await db_manager.init_db()
        logger.info("Database storage initialized successfully")

        self.ad_service = AdService(self.page)
        self.liveliness = LivelinessChecker(self.page)
        self._loading_lock = asyncio.Lock()

        # Gather UMP consent before loading ads
        await self.ad_service.gather_consent()

        # Preload interstitial ad
        await self.ad_service.preload_interstitial()

        # Load saved state
        saved_country = await db_manager.get_setting("user_country")
        if saved_country:
            state.user_country = saved_country
        saved_terms = await db_manager.get_setting("accepted_terms")
        if saved_terms == "true":
            state.has_accepted_terms = True
            state.is_first_launch = False
        saved_theme = await db_manager.get_setting("theme_mode")
        if saved_theme == "dark":
            self.page.theme_mode = ft.ThemeMode.DARK
        elif saved_theme == "light":
            self.page.theme_mode = ft.ThemeMode.LIGHT

        # Load favorites into state — convert set from DB to list for ObservableList support
        urls = await db_manager.get_favorite_urls()
        state.favorites = list(urls)

        # Load history
        state.history = await db_manager.get_history()
        logger.info(
            "State loaded: region=%s, terms=%s, favorites=%d, history=%d",
            state.user_country or "default",
            state.has_accepted_terms,
            len(state.favorites),
            len(state.history),
        )

        # Restore liveliness cache from DB
        from services.liveliness import liveliness_cache

        cached_entries = await db_manager.load_liveliness_cache()
        liveliness_cache.load_from_db(cached_entries)

        # Mount component frontend — AppShell manages routing, theme, nav.
        from app_shell import AppShell
        from state.controller_ctx import (
            ControllerMethods,
            ControllerMethodsCtx,
        )

        methods = ControllerMethods(
            refresh_channels=self.load_channels,
            play_stream=self.play_stream,
            pop_views=self._handle_back,
            push_modal=self.push_modal,
            pop_modal=self.pop_modal,
            close_modal=self.close_modal,
        )
        self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))
        logger.info("AppShell frontend mounted successfully")

        # Startup connectivity check — detect offline on subsequent launches
        async def _startup_connectivity_check():
            try:
                from services.http_client import get_http_client

                client = get_http_client()
                resp = await client.head(
                    "https://www.google.com",
                    timeout=3.0,
                    follow_redirects=True,
                )
                state.is_online = resp.status_code < 400
            except Exception:
                state.is_online = False
                logger.warning("Startup connectivity check: offline")
                try:
                    from utils.notifications import notify_warning

                    notify_warning("You are offline. Some features may be unavailable.")
                except Exception:
                    pass

        asyncio.create_task(_startup_connectivity_check())

    def _on_global_error(self, e):
        err_data = e.data if hasattr(e, "data") else str(e)
        # Suppress errors from the video player stopping (e.g., during back press)
        if self._is_player_closing:
            logger.debug("Global error during player close (suppressed): %s", err_data)
            self._is_player_closing = False
            return
        if self.page.views and any(v.route == "/play" for v in self.page.views):
            logger.debug("Global error during playback (suppressed): %s", err_data)
            return
        logger.error("Global error: %s", err_data)
        try:
            from utils.notifications import notify_warning

            notify_warning(ERR_NETWORK)
        except Exception:
            pass

    async def push_modal(self, name: str) -> None:
        """Push a named modal onto the stack. Call from
        AddCustomContentDialog (or future dialogs) on open."""
        self._modal_stack.append(name)
        self.page.update()

    async def close_modal(self) -> None:
        """Pop the top modal from the stack. Call from
        AddCustomContentDialog on_dismiss and _dismiss."""
        if self._modal_stack:
            self._modal_stack.pop()
        self.page.update()

    async def pop_modal(self, name: str) -> None:
        """Remove a specific named modal (not necessarily the top).

        Useful when a dialog is dismissed via a non-standard path
        and the caller knows exactly which modal to remove."""
        if name in self._modal_stack:
            self._modal_stack.remove(name)
        self.page.update()

    def _handle_back(self):
        """Handle OS back button / FocusScope.on_back.

        If a modal dialog is open (tracked in _modal_stack),
        close it first. Otherwise, fall through to the existing
        view-pop behaviour.
        """
        if self._modal_stack:
            self._modal_stack.pop()
            self.page.update()
            return
        if len(self.page.views) > 1:
            self.page.views.pop()
            self.page.update()

    # --- Channel Loading ---

    async def load_channels(self, force=False):
        from core.app_loader import load_all_channels

        await load_all_channels(self.page, self._loading_lock)

    # --- Playback ---

    async def play_stream(self, url: str, title: str | None = None):
        if self.page.views and any(v.route == "/play" for v in self.page.views):
            logger.warning("Player already active, ignoring duplicate play_stream call")
            return

        if not _is_valid_play_url(url):
            from utils.notifications import notify_error

            notify_error("Invalid or blocked URL.")
            return

        # Save to history
        state.add_to_history(url)
        with contextlib.suppress(Exception):
            await db_manager.save_history(url)

        # Determine title
        if not title or title.strip() == "Stream":
            channel = next((c for c in state.channels if c.get("url") == url), None)
            if channel and channel.get("name"):
                title = channel.get("name")
            else:
                parsed_url = urllib.parse.urlparse(url)
                path_segment = parsed_url.path or ""
                base_name = (
                    os.path.splitext(os.path.basename(path_segment))[0]
                    if path_segment
                    else ""
                )
                if base_name and base_name.lower() not in (
                    "playlist",
                    "index",
                    "manifest",
                    "master",
                    "live",
                    "stream",
                ):
                    title = urllib.parse.unquote(base_name)
                elif parsed_url.netloc:
                    title = parsed_url.netloc
                else:
                    title = "Stream"

        headers = {}
        for pattern, hdrs in CDN_HEADER_OVERRIDES.items():
            if pattern in url:
                headers = hdrs
                break

        # Create player view immediately so the screen isn't blank.
        # Wrap ImmersivePlayer in a FocusScope so Escape/Back while
        # the player is active closes it natively (no parallel
        # page.on_keyboard_event handler). handle_close() runs
        # ImmersivePlayer cleanup (will_unmount) before the view pop.
        async def _player_on_back(e):
            await player.handle_close()
            await self._close_player()

        player = ImmersivePlayer(
            resource=url,
            title=title,
            http_headers=headers,
            on_close=lambda: self._close_player(),
            ad_service=self.ad_service,
        )

        player_view = ft.View(
            route="/play",
            controls=[
                FocusScope(child=player, on_back=_player_on_back),
            ],
            padding=0,
        )

        self.page.views.append(player_view)
        self.page.update()

        # Playback (ad is handled inside player.start_playback)
        await self._safe_start_playback(player)

    def _close_player(self):
        if not self.page.views:
            return
        if len(self.page.views) > 1 and self.page.views[-1].route == "/play":
            self._is_player_closing = True
            self.page.views.pop()
            self.page.update()

    # --- Deep Link ---

    def _handle_deep_link(self, route: str):
        from core.deeplink import parse_deep_link

        url, title = parse_deep_link(route)
        if url:
            logger.info("Deep link URL valid, launching play_stream")
            self.page.run_task(self.play_stream, url, title)

    # --- Routing ---

    async def route_change(self, e=None):
        route = self.page.route
        logger.info("Route changed: %s", route)
        parsed = urllib.parse.urlparse(route)

        # 1. Deep Link from other apps (e.g., AnimePahe TV ktv://)
        if parsed.scheme == "ktv":
            logger.info("KTV deep link detected, clearing views")
            state.is_deep_link_launch = True
            self.page.views.clear()
            self._handle_deep_link(route)
            return

        # 2. "Open With" local video files (Android Intent)
        if parsed.scheme in ("file", "content"):
            if _is_valid_play_url(route):
                self.page.run_task(self.play_stream, route)
            return

        # 2b. Deep Link fallback: Flet strips custom scheme → route is /?url=<base64>
        if parsed.path in ("/", "") and parsed.query:
            query_params = urllib.parse.parse_qs(parsed.query)
            if "url" in query_params:
                logger.info("Deep link fallback detected via query parameter")
                state.is_deep_link_launch = True
                self.page.views.clear()
                reconstructed = f"ktv://play?url={query_params['url'][0]}"
                if "title" in query_params:
                    reconstructed += f"&title={query_params['title'][0]}"
                self._handle_deep_link(reconstructed)
                return

        # 3. AppShell handles all dashboard routing via the component tree.
        # Legacy /dashboard route handler was removed with the old views/ tree.
        # Player views (/play) are pushed by play_stream() above the shell.

    @staticmethod
    def _find_immersive_player(control) -> ImmersivePlayer | None:
        """Recursively walk `.content` and `.controls` to find an ImmersivePlayer
        nested inside FocusScope (KeyboardListener) or other wrappers."""
        if isinstance(control, ImmersivePlayer):
            return control
        if hasattr(control, "content") and control.content is not None:
            found = AppController._find_immersive_player(control.content)
            if found:
                return found
        if hasattr(control, "controls") and control.controls:
            for child in control.controls:
                found = AppController._find_immersive_player(child)
                if found:
                    return found
        return None

    def view_pop(self, e):
        if not self.page.views:
            return
        top = self.page.views[-1]
        player = None
        for control in top.controls:
            player = self._find_immersive_player(control)
            if player:
                break

        if player:
            self.page.run_task(self._close_and_pop, player)
            return

        if len(self.page.views) > 1:
            self.page.views.pop()
            self.page.update()

    async def _close_and_pop(self, player):
        try:
            await player.handle_close()
        except Exception:
            logger.exception("Error closing player")
        if len(self.page.views) > 1:
            self.page.views.pop()
            self.page.update()

    async def _safe_start_playback(self, player):
        try:
            await player.start_playback()
        except Exception:
            logger.exception("Failed to start playback")
            try:
                from utils.notifications import notify_error

                notify_error("Playback failed")
            except Exception:
                pass


async def main(page: ft.Page):
    setup_logging()
    controller = AppController(page)
    await controller.init()

    page.on_route_change = controller.route_change
    page.on_view_pop = controller.view_pop

    # Graceful shutdown: cancel background workers and close resources
    # when the page closes (app exit).
    async def _on_close(e=None):
        from services.liveliness_checker import shutdown_workers as shutdown_liveliness
        from services.logo_cache import shutdown_workers as shutdown_logos

        shutdown_liveliness()
        shutdown_logos()
        with contextlib.suppress(Exception):
            if controller.ad_service:
                await controller.ad_service.close()
        with contextlib.suppress(Exception):
            from services.http_client import close_http_client

            await close_http_client()
        with contextlib.suppress(Exception):
            await db_manager.close()

    page.on_close = _on_close

    await controller.route_change()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
