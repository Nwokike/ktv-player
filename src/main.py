"""KTV Player — main entry point and AppController."""

import asyncio
import contextlib
import logging
import os
import urllib.parse

import flet as ft

import core.logger_handler  # noqa: F401
from app_next.hooks.use_focus_scope import FocusScope
from components.player.immersive_player import ImmersivePlayer
from core.constants import (
    APP_NAME,
    ERR_NETWORK,
)
from core.logging_config import setup_logging
from core.state import state
from core.theme import AppColors, AppTheme
from database.manager import db_manager
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
        # Explicit modal name stack so _handle_back can pop the
        # topmost dialog before popping a view.
        self._modal_stack: list[str] = []

    async def init(self):
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

        # Init services
        await db_manager.init_db()
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
        # else keep SYSTEM (the default from line 56)

        # Load favorites into state — convert set from DB to list for ObservableList support
        urls = await db_manager.get_favorite_urls()
        state.favorites = list(urls)

        # Load history
        state.history = await db_manager.get_history()

        # Restore liveliness cache from DB
        from services.liveliness import liveliness_cache

        cached_entries = await db_manager.load_liveliness_cache()
        liveliness_cache.load_from_db(cached_entries)

        # Mount component frontend — AppShell manages routing, theme, nav.
        from app_next import AppShell
        from app_next.state.controller_ctx import (
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

    def _on_global_error(self, e):
        logger.error("Global error: %s", e.data if hasattr(e, "data") else e)
        try:
            self.page.show_dialog(
                ft.SnackBar(
                    ft.Text(ERR_NETWORK),
                    bgcolor=AppColors.WARNING,
                )
            )
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
        if not _is_valid_play_url(url):
            self.page.show_dialog(
                ft.SnackBar(
                    ft.Text("Invalid or blocked URL."),
                    bgcolor=AppColors.ERROR,
                )
            )
            return

        # Save to history
        state.add_to_history(url)
        with contextlib.suppress(Exception):
            await db_manager.save_history(url)

        # Determine title
        if not title:
            channel = next((c for c in state.channels if c.get("url") == url), None)
            if channel:
                title = channel.get("name", "Stream")
            elif not url.startswith(
                ("http://", "https://", "rtsp://", "rtmp://", "rtp://", "mms://")
            ):
                title = os.path.splitext(os.path.basename(url))[0]
            else:
                title = "Stream"

        # Automatically inject headers for specific CDNs (e.g. Kwik/AnimePahe)
        headers = {}
        if "owocdn.top" in url or "uwucdn.top" in url or "kwik" in url:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://kwik.cx/",
            }

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
        if len(self.page.views) > 1 and self.page.views[-1].route == "/play":
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

    def view_pop(self, e):
        if not self.page.views:
            return
        top = self.page.views[-1]
        for control in top.controls:
            if isinstance(control, ImmersivePlayer):
                self.page.run_task(self._close_and_pop, control)
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


async def main(page: ft.Page):
    setup_logging()
    controller = AppController(page)
    await controller.init()

    page.on_route_change = controller.route_change
    page.on_view_pop = controller.view_pop

    await controller.route_change()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
