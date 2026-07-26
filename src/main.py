"""KTV Player — main entry point and AppController."""

import asyncio
import base64
import contextlib
import logging
import os
import re
import urllib.parse

import flet as ft

from channels.provider import channel_provider
from components.player.immersive_player import ImmersivePlayer
from core.constants import (
    APP_NAME,
    ERR_NETWORK,
)
from core.focus_manager import FocusManager
import core.logger_handler  # noqa: F401
from core.logging_config import setup_logging
from core.state import state
from core.theme import AppColors, AppTheme
from database.manager import db_manager
from services.ad_service import AdService
from services.iptv_service import iptv_service
from services.liveliness_checker import LivelinessChecker

logger = logging.getLogger(__name__)

from core.url_validator import _is_valid_play_url


class AppController:
    def __init__(self, page: ft.Page):
        self.page = page
        self.ad_service: AdService | None = None
        self.liveliness: LivelinessChecker | None = None
        self.focus_manager: FocusManager | None = None
        self._loading_lock: asyncio.Lock | None = None

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
        if saved_theme:
            self.page.theme_mode = (
                ft.ThemeMode.DARK if saved_theme == "dark" else ft.ThemeMode.LIGHT
            )

        # Load favorites into state for O(1) lookups
        state.favorites = await db_manager.get_favorite_urls()

        # Load history
        state.history = await db_manager.get_history()

        # Restore liveliness cache from DB
        from services.liveliness import liveliness_cache

        cached_entries = await db_manager.load_liveliness_cache()
        liveliness_cache.load_from_db(cached_entries)

        # Focus manager
        self.focus_manager = FocusManager(self.page)
        self.focus_manager.set_back_handler(self._handle_back)

    def _on_global_error(self, e):
        logger.error("Global error: %s", e.data if hasattr(e, "data") else e)
        try:
            self.page.snack_bar = ft.SnackBar(
                ft.Text(ERR_NETWORK),
                bgcolor=AppColors.WARNING,
            )
            self.page.snack_bar.open = True
            self.page.update()
        except Exception:
            pass

    def _handle_back(self):
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
            self.page.snack_bar = ft.SnackBar(
                ft.Text("Invalid or blocked URL."),
                bgcolor=AppColors.ERROR,
            )
            self.page.snack_bar.open = True
            self.page.update()
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

        # Create player view immediately so the screen isn't blank
        player = ImmersivePlayer(
            resource=url,
            title=title,
            http_headers=headers,
            on_close=lambda: self._close_player(),
            ad_service=self.ad_service,
        )

        player_view = ft.View(
            route="/play",
            controls=[player],
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

        # 3. Standard Routing
        if parsed.path in ("/", ""):
            self.page.views.clear()
            self.page.run_task(self._startup_flow)

        elif parsed.path == "/dashboard":
            self.page.views.clear()
            from views.dashboard import build_dashboard_view

            view = build_dashboard_view(
                page_obj=self.page,
                on_play=self.play_stream,
                ad_service=self.ad_service,
                liveliness=self.liveliness,
                load_channels=self.load_channels,
            )
            self.page.views.append(view)
            self.page.update()

    async def _startup_flow(self):
        from core.startup import run_startup_flow
        await run_startup_flow(self)

    async def _onboarding_complete(self):
        from core.startup import complete_onboarding
        await complete_onboarding(self)

    async def _go_to_dashboard(self):
        from core.startup import go_to_dashboard
        await go_to_dashboard(self)

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
