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
    MSG_OFFLINE,
    MSG_ONLINE,
)
from core.logging_config import setup_logging
from core.state import state
from core.theme import AppTheme
from database.manager import db_manager
from hooks.use_focus_scope import FocusScope
from services.ad_service import AdService
from services.hls_proxy import HLSProxy
from services.liveliness_checker import LivelinessChecker

logger = logging.getLogger(__name__)

from core.url_validator import _is_valid_play_url, is_local_media_url


class AppController:
    def __init__(self, page: ft.Page):
        self.page = page
        self.ad_service: AdService | None = None
        self.liveliness: LivelinessChecker | None = None
        self._loading_lock: asyncio.Lock | None = None
        # Separate from _loading_lock: channel loading must never block or
        # drop a playback request. v2.0.2 (549503a) made play_stream share
        # the loading lock, so a cold-start deep link was silently dropped
        # while the loader fetched remote playlists — a permanent blank
        # screen. This lock only suppresses duplicate concurrent plays.
        self._play_lock: asyncio.Lock | None = None
        self._is_player_closing: bool = False
        # True while a deep-linked video is the only view — closing it exits
        # to the calling app instead of popping to a cleared view stack.
        self._deep_link_open: bool = False
        self.hls_proxy: HLSProxy | None = None
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

        self.hls_proxy = HLSProxy()
        await self.hls_proxy.start()

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
        from services.update_service import UpdateService

        self.update_service = UpdateService()
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

        # Lifecycle safety net: when the app is hidden (minimize, home),
        # persist the top player's position best-effort. Covers the exits
        # flet doesn't hook with an event (Android killing the app while
        # hidden) — pairs with the 10s in-play checkpoints.
        page = self.page
        _controller = self
        _previous_lifecycle = page.on_app_lifecycle_state_change

        def _on_lifecycle_save(e):
            if getattr(e, "data", None) == "hidden":
                logger.info("close-path: lifecycle hidden -> checkpoint save")
                _controller._save_top_player_position()
            if _previous_lifecycle is not None:
                result = _previous_lifecycle(e)
                if hasattr(result, "__await__"):
                    with contextlib.suppress(Exception):
                        page.run_task(result)

        page.on_app_lifecycle_state_change = _on_lifecycle_save

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
            check_for_updates=self.check_for_updates,
            open_version_dialog=self.open_version_dialog,
        )
        self.page.render(lambda: ControllerMethodsCtx(methods, lambda: AppShell()))
        logger.info("AppShell frontend mounted successfully")

        # Connectivity service — replaces DNS-probe polling with native listener
        connectivity = ft.Connectivity()
        connectivity.on_change = self._on_connectivity_change
        self.page.services.append(connectivity)

        async def _init_connectivity():
            from flet import ConnectivityType

            try:
                result = await connectivity.get_connectivity()
                state.is_online = ConnectivityType.NONE not in result
            except Exception:
                pass

        self.page.run_task(_init_connectivity)

        # Update check in the background — pure GET + observable flip, so
        # it can never delay the deep-link fast path. Mandatory updates
        # open the version dialog on arrival.
        self.page.run_task(self.check_for_updates)

    async def check_for_updates(self, notify_if_latest: bool = False) -> None:
        """Check version.json on main for a newer build or announcement.
        Silent on failure; only a mandatory update auto-opens the dialog."""
        if not getattr(self, "update_service", None):
            return
        update_info = await self.update_service.check_for_update()
        if update_info:
            state.update_available = True
            state.update_data = update_info
            logger.info(
                "Update available: v%s (build %s, type=%s)",
                update_info.get("version"),
                update_info.get("build_number"),
                update_info.get("type"),
            )
            if update_info.get("mandatory"):
                self.open_version_dialog()
        elif notify_if_latest:
            from core.constants import APP_VERSION
            from utils.notifications import notify

            notify(f"✓ {APP_VERSION} is up to date")

    def open_version_dialog(self) -> None:
        """Open the version dialog (changelog when up to date, update UI
        when a newer build was found)."""
        from components.version_dialog import show_version_dialog

        show_version_dialog(self.page)

    def _on_connectivity_change(self, e):
        from flet import ConnectivityType

        was_online = state.is_online
        state.is_online = ConnectivityType.NONE not in e.connectivity
        if was_online and not state.is_online:
            logger.warning("Connectivity lost")
            # Reset liveliness to neutral — failed probes while offline would
            # paint every dot red. Checks resume on reconnect.
            from services.liveliness import liveliness_cache

            liveliness_cache.clear()
            try:
                from utils.notifications import notify_warning

                notify_warning(MSG_OFFLINE, persist=True)
            except Exception:
                pass
        elif not was_online and state.is_online:
            logger.info("Connectivity restored")
            try:
                from utils.notifications import notify

                notify(MSG_ONLINE)
            except Exception:
                pass

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

    async def play_stream(
        self,
        url: str,
        title: str | None = None,
        referer: str | None = None,
        headers: dict | None = None,
        from_deep_link: bool = False,
    ):
        if not self._play_lock:
            self._play_lock = asyncio.Lock()

        if self._play_lock.locked():
            logger.info("play_stream locked, ignoring duplicate request")
            return

        async with self._play_lock:
            await self._do_play_stream(url, title, referer, headers, from_deep_link)

    async def _do_play_stream(
        self,
        url: str,
        title: str | None = None,
        referer: str | None = None,
        headers: dict | None = None,
        from_deep_link: bool = False,
    ):
        if not _is_valid_play_url(url):
            logger.warning("play_stream called with invalid URL: %s", url)
            from utils.notifications import notify_error

            notify_error("Invalid or blocked URL.")
            return

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
                    "uwu",
                ):
                    title = urllib.parse.unquote(base_name)
                elif parsed_url.netloc:
                    title = parsed_url.netloc
                else:
                    title = "Stream"

        # Save to history with resolved title
        state.add_to_history(url, title)
        with contextlib.suppress(Exception):
            await db_manager.save_history(url, title)

        headers = headers or {}
        referer_header = referer or headers.get("Referer")

        for pattern, hdrs in CDN_HEADER_OVERRIDES.items():
            if pattern in url:
                if not headers:
                    headers = hdrs
                if not referer_header:
                    referer_header = hdrs.get("Referer")
                break

        resource_url = url
        if self.hls_proxy and (
            referer_header or headers or any(p in url for p in CDN_HEADER_OVERRIDES)
        ):
            resource_url = self.hls_proxy.get_proxy_url(
                target_url=url,
                referer=referer_header,
                headers=headers,
            )

        # Create player view immediately so the screen isn't blank.
        # Wrap ImmersivePlayer in a FocusScope so Escape/Back while
        # the player is active closes it natively (no parallel
        # page.on_keyboard_event handler). handle_close() runs
        # ImmersivePlayer cleanup (will_unmount) before the view pop.
        async def _player_on_back(e):
            await player.handle_close()
            self._close_player()

        # Favorite star only for in-app channel plays — deep links AND local
        # videos open the player without it (history is saved for both).
        # Source metadata lets the player re-pin quality/audio via the proxy.
        player = ImmersivePlayer(
            resource=resource_url,
            title=title,
            http_headers=headers,
            on_close=lambda: self._close_player(),
            ad_service=self.ad_service,
            show_favorite=not (from_deep_link or is_local_media_url(url)),
            hls_proxy=self.hls_proxy,
            source_url=url,
            source_referer=referer_header,
            source_headers=headers or None,
            source_proxied=resource_url != url,
        )

        player_view = ft.View(
            route="/play",
            controls=[
                FocusScope(child=player, on_back=_player_on_back),
            ],
            padding=0,
        )

        # Deep-linked players are the only view (the shell was cleared at
        # the deep-link launch) — closing them exits to the caller app.
        self._deep_link_open = from_deep_link

        self.page.views.append(player_view)
        self.page.update()

        # Playback (ad is handled inside player.start_playback)
        await self._safe_start_playback(player)

    def _close_player(self):
        if not self.page.views:
            return
        if self._deep_link_open and self.page.views[-1].route == "/play":
            # A deep-linked video sits on the blank underlay view (the shell
            # was cleared at launch) — closing it returns to the caller.
            # Checked BEFORE the plain pop branch: the underlay makes
            # len(views) > 1 true for deep links too.
            player = self._find_immersive_player(self.page.views[-1].controls[0])
            if player and not (
                getattr(player, "_is_closing", False)
                and getattr(player, "_position_saved", False)
            ):
                # Closing but not yet saved (e.g. a close raced in) — still
                # run the awaited close-save so the position is persisted.
                player._is_closing = True
                self.page.run_task(self._close_player_with_save, player)
                return
            self.page.run_task(self._exit_to_caller)
        elif len(self.page.views) > 1 and self.page.views[-1].route == "/play":
            self._is_player_closing = True
            self.page.views.pop()
            self.page.update()

    async def _exit_to_caller(self):
        """Finish the app after a deep-linked video closes. The deep-link
        launch cleared the shell, so there is no in-app screen to return
        to — MX-Player-style back-to-caller. Flet's window.close() is a
        desktop-only no-op on Android (flet's Dart closeWindow() guards
        isDesktopPlatform()), so the exit is activity.finish() via jnius."""
        self._deep_link_open = False
        from services import pip_service

        # Reset PiP auto-enter before finishing so the activity can never
        # re-enter PiP once the app is gone.
        await asyncio.to_thread(pip_service.set_auto_pip, False)
        exited = await asyncio.to_thread(pip_service.exit_app)
        if not exited:
            try:
                await self.page.window.close()
            except Exception:
                pass

    # --- Deep Link ---

    def _handle_deep_link(self, route: str):
        from core.deeplink import parse_deep_link

        url, title, referer, headers = parse_deep_link(route)
        if url:
            logger.info("Deep link URL valid, launching play_stream")
            self.page.run_task(self.play_stream, url, title, referer, headers, True)

    # --- Routing ---

    async def route_change(self, e=None):
        route = self.page.route
        logger.info("Route changed: %s", route)
        parsed = urllib.parse.urlparse(route)

        # Stop any active player when navigating away from /play
        if route != "/play" and self.page.views:
            for v in self.page.views:
                if v.route == "/play":
                    for ctrl in v.controls:
                        player = self._find_immersive_player(ctrl)
                        if player and not (
                            getattr(player, "_is_closing", False)
                            and getattr(player, "_position_saved", False)
                        ):
                            logger.info(
                                "close-path: route_change away from /play -> close-save"
                            )
                            player._is_closing = True
                            player._is_final_error = True
                            # Route through the awaited close-save so the
                            # position is persisted BEFORE playback stops.
                            # The old bare stop marked _is_closing without
                            # saving, which made view_pop's "already
                            # closing" guard skip its save whenever this
                            # event won the back-press race.
                            self.page.run_task(self._close_player_with_save, player)
                    break

        # 1. Deep Link from external apps or web browsers (ktv://)
        if parsed.scheme == "ktv":
            logger.info("KTV deep link detected, clearing views")
            state.is_deep_link_launch = True
            self.page.views.clear()
            # Blank underlay beneath the player: flet's Dart system-back
            # handler returns early when the top view is the ONLY view
            # (page.dart _handleSystemPopRoute: views.length <= 1 → the
            # framework pops → SystemNavigator.pop() — the activity exits
            # without any Python event, so no close path can save the
            # resume position). A view beneath the player keeps system
            # back on the view_pop path: awaited save, then exit-to-caller.
            self.page.views.append(
                ft.View(route="/blank", bgcolor=ft.Colors.BLACK, padding=0)
            )
            self._handle_deep_link(route)
            return

        # 2. "Open With" local video files (Android Intent)
        if parsed.scheme in ("file", "content"):
            if _is_valid_play_url(route):
                # Normalize SAF content:// URIs to the canonical
                # /storage/emulated/0/... path so an "Open With" play and a
                # Local-screen play of the same file share ONE history key
                # (resume positions included).
                from services.local_scanner import resolve_saf_path

                resolved = resolve_saf_path(route)
                if resolved != route and _is_valid_play_url(resolved):
                    route = resolved
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
            logger.info("close-path: view_pop ignored (no views)")
            return
        top = self.page.views[-1]
        player = None
        for control in top.controls:
            player = self._find_immersive_player(control)
            if player:
                break

        if player:
            if getattr(player, "_is_closing", False) and getattr(
                player, "_position_saved", False
            ):
                # A close already ran and saved this position.
                logger.info("close-path: view_pop skipped (already closing+saved)")
                return
            logger.info(
                "close-path: view_pop -> close-save (was_closing=%s)",
                getattr(player, "_is_closing", False),
            )
            player._is_closing = True
            # The position save must be AWAITED before the view pops (and,
            # on deep links, before activity.finish()). The previous
            # fire-and-forget create_task was routinely killed by Android
            # at teardown — resume worked on desktop (its event loop
            # survives) but never on phone.
            self.page.run_task(self._close_player_with_save, player)
            return

        logger.info("close-path: view_pop without player, popping view")
        if len(self.page.views) > 1:
            self.page.views.pop()
            self.page.update()

    async def _close_player_with_save(self, player):
        """Persist position (awaited), then stop playback and pop/exit."""
        await self._persist_player_position(player)

        # Stop synchronously: clear playlist + update() queues a
        # platform channel message that halts native playback immediately.
        try:
            player.video.playlist = []
            player.video.update()
        except Exception:
            pass

        if self._deep_link_open:
            # Deep-linked player: back exits to the caller app. Checked
            # before the plain pop — the blank underlay keeps a second view
            # beneath the player, so len(views) > 1 is true here too.
            self._deep_link_open = False
            logger.info("close-path: close-save -> exit to caller")
            await self._exit_to_caller()
        elif len(self.page.views) > 1:
            logger.info("close-path: close-save -> pop view")
            self._is_player_closing = True
            self.page.views.pop()
            self.page.update()

    def _save_top_player_position(self):
        """Best-effort checkpoint save for the top-most player (lifecycle
        'hidden'). Fire-and-forget: the app is being hidden, so the loop
        may only have a moment — better a late checkpoint than none."""
        if not self.page.views:
            return
        for ctrl in self.page.views[-1].controls:
            player = self._find_immersive_player(ctrl)
            if player and not getattr(player, "_is_closing", False):
                try:
                    self.page.run_task(self._persist_player_position, player)
                except Exception:
                    logger.debug("Lifecycle checkpoint save failed", exc_info=True)
                return

    async def _persist_player_position(self, player) -> None:
        """VOD-only position save, awaited so it completes before teardown."""
        try:
            pos_sec = player._last_position
            dur_sec = player._last_duration
            if player.source_url and dur_sec > 0 and pos_sec > 3:
                if pos_sec >= (dur_sec - 5):
                    pos_sec = 0.0
                await db_manager.update_history_position(
                    player.source_url, pos_sec, dur_sec
                )
                player._position_saved = True
                logger.info(
                    "close-path: position saved (%s at %.1fs of %.1fs)",
                    str(player.source_url)[:80],
                    pos_sec,
                    dur_sec,
                )
            else:
                logger.info(
                    "close-path: position save skipped (has_url=%s dur=%.1f pos=%.1f)",
                    bool(player.source_url),
                    dur_sec,
                    pos_sec,
                )
        except Exception:
            logger.debug("Persisting position on close failed", exc_info=True)

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

        # Stop any active video player before tearing down services
        with contextlib.suppress(Exception):
            if controller.page.views:
                for v in controller.page.views:
                    for ctrl in v.controls:
                        player = controller._find_immersive_player(ctrl)
                        if player:
                            player._is_closing = True
                            with contextlib.suppress(Exception):
                                await player.video.stop()
                            player.video.playlist = []
                            player.video.update()

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
