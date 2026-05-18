import asyncio
import base64
import contextlib
import ipaddress
import logging
import re
import time  # <-- Added time for the cache-buster
import urllib.parse

import flet as ft

from components.player.immersive_player import ImmersivePlayer
from core.constants import DEEP_LINK_PLAY_PREFIX, SPLASH_DURATION
from core.crash_reporter import install_crash_handler
from core.focus_manager import FocusManager
from core.state import state
from core.theme import AppColors, AppTheme
from database.manager import db_manager
from services.ad_service import AdService
from services.iptv_service import iptv_service
from services.liveliness import liveliness_cache
from views.dashboard import build_dashboard_view
from views.onboarding import build_onboarding_view
from views.player_view import build_player_view
from views.splash import build_splash_view

logger = logging.getLogger(__name__)

_IS_WINDOWS_PATH = re.compile(r"^[A-Za-z]:[\\/]", re.IGNORECASE)

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
]

_SENSITIVE_PATHS = re.compile(
    r"(?:/etc/|/proc/|/sys/|/dev/|Windows/|Program\sFiles|Users/.*\.ssh|\.env)",
    re.IGNORECASE,
)


def _is_blocked_ip(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
        return any(ip in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        return False


def _is_valid_play_url(url: str) -> bool:
    if url.startswith(("http://", "https://")):
        try:
            parsed = urllib.parse.urlparse(url)
            host = parsed.hostname or ""
            if _is_blocked_ip(host):
                return False
            if host.lower() in ("localhost", "metadata.google.internal"):
                return False
            if parsed.username or parsed.password:
                return False
        except Exception:
            return False
        return True
    if url.startswith("file://"):
        path = url[7:]
        return not _SENSITIVE_PATHS.search(path)
    if url.startswith("/"):
        return not _SENSITIVE_PATHS.search(url)
    return bool(_IS_WINDOWS_PATH.match(url)) and not _SENSITIVE_PATHS.search(url)


class AppController:
    def __init__(self, page: ft.Page):
        self.page = page
        self.ad_service = AdService(page)
        self.focus_manager = FocusManager(page)
        self.liveliness_checker = None
        self._loading_lock = asyncio.Lock()
        self._channels_loaded = False
        self._resource_locks: dict[str, asyncio.Lock] = {}
        self._current_player = None

        page.on_app_lifecycle_state_change = self._handle_lifecycle

    async def _handle_lifecycle(self, e):
        state_str = getattr(e, "state", e.data)
        if state_str in ["pause", "hidden"]:
            state.is_loading = False
        self.page.update()

    def _get_liveliness(self):
        if self.liveliness_checker is None:
            from services.liveliness_checker import LivelinessChecker
            self.liveliness_checker = LivelinessChecker(
                self.page, iptv_service.get_client()
            )
        return self.liveliness_checker

    async def init(self):
        self.page.title = "KTV Player"
        self.page.favicon = "icon.png"

        install_crash_handler(self.page)

        def global_error_handler(e):
            self.page.snack_bar = ft.SnackBar(
                ft.Text("Stream unavailable or network timeout."),
                bgcolor=AppColors.WARNING,
            )
            self.page.snack_bar.open = True
            self.page.update()

        self.page.on_error = global_error_handler

        self.page.fonts = {
            "Outfit": "assets/outfit.css"
        }
        self.page.theme = AppTheme.get_light_theme()
        self.page.dark_theme = AppTheme.get_dark_theme()
        self.page.theme.font_family = "Outfit"
        self.page.dark_theme.font_family = "Outfit"
        self.page.theme_mode = ft.ThemeMode.SYSTEM
        saved_theme = await db_manager.get_setting("theme_mode", "")
        if saved_theme == "light":
            self.page.theme_mode = ft.ThemeMode.LIGHT
        elif saved_theme == "dark":
            self.page.theme_mode = ft.ThemeMode.DARK
        state.theme_mode = self.page.theme_mode
        self.page.padding = 0
        self.page.spacing = 0

        self.page.run_task(self.ad_service.preload_interstitial)

        await db_manager.init_db()

        state.user_country = await db_manager.get_setting("user_country", "")
        state.has_accepted_terms = await db_manager.get_setting("has_accepted_terms", "false") == "true"
        state.is_first_launch = not state.has_accepted_terms

        db_history = await db_manager.get_history()
        state.history = db_history

        self.focus_manager.set_back_handler(self._handle_global_back)

    def _pop_play_view(self):
        self._current_player = None
        if len(self.page.views) > 1:
            self.page.views.pop()
            self.page.route = self.page.views[-1].route  # FIX: Reset internal route
            self.page.update()

    def _handle_global_back(self):
        logger.debug("_handle_global_back, views=%d", len(self.page.views))
        if len(self.page.views) > 1:
            top_view = self.page.views[-1]
            route = getattr(top_view, "route", "")
            logger.debug("back from route=%s", route)

            if route.startswith("/play"):
                if self._current_player:
                    self.page.run_task(self._current_player.handle_close)
                    self._current_player = None
                self.page.views.pop()
                self.page.route = self.page.views[-1].route  # FIX: Reset internal route
                self.page.update()
            else:
                self.page.views.pop()
                self.page.route = self.page.views[-1].route  # FIX: Reset internal route
                self.page.update()

    def view_pop(self, e: ft.ViewPopEvent):
        logger.debug("view_pop, views=%d", len(self.page.views))
        if len(self.page.views) > 1:
            top_view = self.page.views[-1]
            route = getattr(top_view, "route", "")
            logger.debug("view_pop from route=%s", route)
            if route.startswith("/play") and self._current_player:
                self.page.run_task(self._current_player.handle_close)
                self._current_player = None
            self.page.views.pop()
            self.page.route = self.page.views[-1].route  # FIX: Reset internal route
            self.page.update()

    async def navigate(self, route: str):
        await self.page.push_route(route)

    async def play_stream(self, url: str):
        logger.debug("play_stream called, url=%s", url[:60])
        if self._current_player:
            with contextlib.suppress(Exception):
                await self._current_player.handle_close()
            self._current_player = None

        await db_manager.save_history(url)
        state.add_to_history(url)
        encoded_url = base64.urlsafe_b64encode(url.encode()).decode()

        await self.ad_service.show_interstitial()

        # THE CACHE BUSTER: Appending &t=timestamp forces Flet to treat this as a 100% new navigation
        await self.navigate(f"/play?url={encoded_url}&t={time.time()}")

    async def load_channels(self, force: bool = False):
        logger.debug("load_channels called, force=%s, _channels_loaded=%s", force, self._channels_loaded)
        async with self._loading_lock:
            if self._channels_loaded and not force:
                logger.debug("load_channels skipped (already loaded)")
                return

            self._channels_loaded = False
            state.is_loading = True
            logger.debug("load_channels: refreshing dashboard (loading state)")
            if hasattr(self.page, "refresh_dashboard"):
                self.page.refresh_dashboard()
            else:
                self.page.update()

            try:
                all_channels = await iptv_service.load_all_sources()
                logger.debug("load_channels: got %d channels", len(all_channels))
                state.channels = all_channels
                from views.tabs import _invalidate_groups_cache
                _invalidate_groups_cache()
                self._channels_loaded = True
            finally:
                state.is_loading = False
                logger.debug("load_channels: refreshing dashboard (done)")
                if hasattr(self.page, "refresh_dashboard"):
                    self.page.refresh_dashboard()
                else:
                    self.page.update()

    def reset_channels_loaded(self):
        self._channels_loaded = False

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._resource_locks:
            self._resource_locks[key] = asyncio.Lock()
        return self._resource_locks[key]

    async def start_splash_timer(self):
        await asyncio.sleep(SPLASH_DURATION)
        dest = "/dashboard" if not state.is_first_launch else "/onboarding"
        await self.navigate(dest)

    def _parse_deep_link(self, route: str) -> str | None:
        if route.startswith(DEEP_LINK_PLAY_PREFIX):
            encoded = route[len(DEEP_LINK_PLAY_PREFIX):]
            return encoded
        return None

    async def route_change(self, e: ft.RouteChangeEvent | None = None):
        route = self.page.route
        parsed_url = urllib.parse.urlparse(route)

        if parsed_url.path in ["/", "/dashboard", "/onboarding"]:
            self.page.views.clear()

        try:
            if parsed_url.path == "/":
                self.page.views.append(build_splash_view(self.page))
                self.page.run_task(self.start_splash_timer)

            elif parsed_url.path == "/onboarding":
                self.page.views.append(
                    build_onboarding_view(
                        page_obj=self.page,
                        on_complete=lambda: self.page.run_task(self.navigate, "/dashboard"),
                    )
                )
                if not state.channels:
                    self.page.run_task(self.load_channels)

            elif parsed_url.path == "/dashboard":
                logger.debug("route_change: /dashboard, state.channels=%d", len(state.channels))
                self.page.views.append(
                    build_dashboard_view(
                        page_obj=self.page,
                        on_play=self.play_stream,
                        ad_service=self.ad_service,
                    )
                )
                if not state.channels:
                    logger.debug("route_change: /dashboard triggering load_channels")
                    self.page.run_task(self.load_channels)
                else:
                    logger.debug("route_change: /dashboard skipping load_channels (already loaded)")

            elif parsed_url.path == "/play":
                params = urllib.parse.parse_qs(parsed_url.query)
                encoded_url = params.get("url", [None])[0]
                logger.debug("/play encoded_url=%s", encoded_url[:40] if encoded_url else None)
                if encoded_url:
                    try:
                        padding = "=" * (-len(encoded_url) % 4)
                        padded_url = encoded_url + padding
                        url = base64.urlsafe_b64decode(padded_url).decode()
                        if not _is_valid_play_url(url):
                            logger.debug("/play rejected invalid url scheme: %s", url[:60])
                            self.page.run_task(self.navigate, "/dashboard")
                            return
                        logger.debug("/play route, url=%s", url[:60])
                        player = ImmersivePlayer(resource=url, on_close=lambda: self._pop_play_view())
                        self._current_player = player
                        logger.debug("ImmersivePlayer created, building view...")
                        self.page.views.append(
                            build_player_view(
                                page_obj=self.page,
                                url=url,
                                on_back=lambda: self._pop_play_view(),
                                player=player,
                            )
                        )
                        logger.debug("player view appended")
                    except Exception:
                        logger.exception("/play error")
                        self.page.run_task(self.navigate, "/dashboard")
                else:
                    logger.debug("/play no url param")
                    self.page.run_task(self.navigate, "/dashboard")
        except Exception:
            logger.exception("route_change error")
            self.page.snack_bar = ft.SnackBar(
                ft.Text("An error occurred. Please restart the app."),
                bgcolor=AppColors.ERROR,
            )
            self.page.snack_bar.open = True

        self.page.update()

    async def cleanup(self):
        liveliness_cache.clear()
        if self.liveliness_checker:
            await self.liveliness_checker.close()
        await iptv_service.close()
        await db_manager.close()


async def main(page: ft.Page):
    controller = AppController(page)
    await controller.init()

    page.load_channels = controller.load_channels
    page.get_liveliness = controller._get_liveliness

    page.on_route_change = controller.route_change
    page.on_view_pop = controller.view_pop

    async def on_unload(e):
        await controller.cleanup()

    page.on_unload = on_unload

    await controller.route_change()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")