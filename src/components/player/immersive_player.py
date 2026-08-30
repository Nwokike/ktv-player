import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import Any

import flet as ft
import flet_video as fv

from core.theme import AppColors
from database.manager import db_manager
from services.youtube_resolver import is_youtube_url
from utils.notifications import (
    register_fullscreen_toast,
    set_fullscreen_toast_active,
    unregister_fullscreen_toast,
)

logger = logging.getLogger(__name__)

# Absolute backstop: if no load/position/error event arrives within this
# window, the loading/reconnecting overlay is replaced by the retry/back UI.
# mpv's network-timeout (10s) usually errors out first with a real reason.
_WATCHDOG_SECONDS = 20.0


def _short_variant_label(variant: dict) -> str:
    """Compact chip label: '1280x720' → '720p', else bandwidth."""
    resolution = variant.get("resolution") or ""
    if "x" in resolution:
        return f"{resolution.split('x')[-1]}p"
    bandwidth = variant.get("bandwidth", 0)
    if bandwidth >= 1_000_000:
        return f"{bandwidth / 1_000_000:.0f}M"
    return f"V{(variant.get('index') or 0) + 1}"


class ImmersivePlayer(ft.Stack):
    def __init__(
        self,
        resource: str,
        on_close: Callable | None = None,
        title: str = "",
        autoplay: bool = True,
        volume: float = 100.0,
        muted: bool = False,
        http_headers: dict | None = None,
        ad_service: Any | None = None,
        show_favorite: bool = True,
        hls_proxy: Any | None = None,
        source_url: str = "",
        source_referer: str | None = None,
        source_headers: dict | None = None,
        source_proxied: bool = False,
    ):
        super().__init__()
        self.resource = resource
        self._original_resource = resource
        self.on_close = on_close
        self.title = title
        self.http_headers = http_headers or {}
        self.ad_service = ad_service
        # Deep-link plays (ktv://) hide the in-player favorite star
        self.show_favorite_button = show_favorite
        self.expand = True

        # Quality / audio-track switching (HLS proxy manifest pinning)
        self.hls_proxy = hls_proxy
        self.source_url = source_url or resource
        self.source_referer = source_referer
        self.source_headers = source_headers
        self.source_proxied = source_proxied
        self._current_variant: int | None = None
        self._current_audio: str | None = None
        self._variants_cache: list[dict] | None = None
        self._audio_tracks_cache: list[dict] | None = None
        # Resume-from-last-position: one-shot seek consumed by the first
        # position-change tick after playback starts. _pending_seek is set
        # by _swap_media; _initial_resume_position comes from history.
        self._pending_seek: float | None = None
        self._initial_resume_position: float | None = None
        self._last_position: float = 0.0
        self._last_duration: float = 0.0
        try:
            entry = db_manager.get_history_entry_sync(self.source_url)
        except Exception:
            entry = None
        if entry and entry.get("position") is not None:
            try:
                saved_pos = float(entry["position"])
                saved_dur = float(entry["duration"]) if entry.get("duration") else None
                # Skip resume if finished (within 5s of end) or < 3s
                if saved_pos > 3 and (
                    saved_dur is None or saved_pos < max(0, saved_dur - 5)
                ):
                    self._initial_resume_position = saved_pos
                    if saved_dur is not None:
                        self._last_duration = saved_dur
            except TypeError, ValueError:
                self._initial_resume_position = None

        # Android PiP availability (detected without page context — jnius
        # only resolves on Android)
        self.pip_available = False
        try:
            from services.pip_service import is_pip_supported

            self.pip_available = is_pip_supported()
        except Exception:
            self.pip_available = False

        self._retry_count = 0
        self._reconnect_count = 0
        self._is_final_error = False
        self._is_closing = False
        self._was_closed_during_ad = False
        # Auto-PiP is armed (True) only while video is actually playing.
        self._pip_active = False
        self._watchdog_task: asyncio.Task | None = None

        # Overlay Controls
        self.status_text = ft.Text(
            "Loading stream...",
            size=15,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_500,
            text_align=ft.TextAlign.CENTER,
        )
        self.loading_ring = ft.ProgressRing(
            width=48,
            height=48,
            stroke_width=4,
            color=AppColors.PRIMARY,
        )

        # Error Overlay Action Buttons
        self.retry_btn = ft.OutlinedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.REFRESH_ROUNDED, size=18),
                    ft.Text("Retry Stream", size=13),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=lambda e: self.page.run_task(self._manual_retry),
            visible=False,
        )
        self.back_error_btn = ft.FilledButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ARROW_BACK_ROUNDED, size=18),
                    ft.Text("Go Back", size=13),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            on_click=lambda e: self.page.run_task(self._on_back),
            visible=False,
        )
        self.error_actions_row = ft.Row(
            controls=[self.retry_btn, self.back_error_btn],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=16,
            visible=False,
        )

        self.overlay = ft.Container(
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.BLACK),
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    self.loading_ring,
                    ft.Container(height=16),
                    self.status_text,
                    ft.Container(height=16),
                    self.error_actions_row,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )
        self._overlay_hidden = False

        # Speed control
        self._speed_idx = 2  # index of 1.0 in speeds list
        self._speeds = [0.25, 0.5, 1.0, 1.25, 1.5, 2.0]
        self.speed_text = ft.Text(
            "1.0x",
            size=11,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_600,
        )

        self.video = fv.Video(
            autoplay=autoplay,
            expand=True,
            volume=volume,
            muted=muted,
            wakelock=True,
            filter_quality=ft.FilterQuality.LOW,
            pause_upon_entering_background_mode=True,
            resume_upon_entering_foreground_mode=True,
            playlist_mode=fv.PlaylistMode.NONE,
            subtitle_track=fv.VideoSubtitleTrack.auto(),
            subtitle_configuration=fv.VideoSubtitleConfiguration(
                text_style=ft.TextStyle(
                    size=22.0,
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.W_600,
                    bgcolor=ft.Colors.BLACK_54,
                ),
                text_align=ft.TextAlign.CENTER,
                visible=True,
            ),
            configuration=fv.VideoConfiguration(
                enable_hardware_acceleration=True,
                # hwdec left at the flet_video platform default (Android:
                # "auto-safe", desktop: "auto"). The previous hard force of
                # "mediacodec" made phone MKVs fail with "Could not open
                # codec" — auto-safe still uses MediaCodec when the device
                # supports the codec, but falls back to software decoding
                # instead of erroring out.
                mpv_properties={
                    "cache": "yes",
                    "cache-secs": 5,
                    "demuxer-max-bytes": "50M",
                    "demuxer-max-back-bytes": "10M",
                    "framedrop": "vo",
                    "hr-seek-framedrop": "yes",
                    # mpv default is 60s — dead hosts would spin the loading
                    # overlay for a minute with no error event. 10s makes
                    # failure deterministic (verified: mpv DOCS/man/options.rst).
                    "network-timeout": 10,
                },
            ),
            fill_color=ft.Colors.BLACK,
            fit=ft.BoxFit.CONTAIN,
            alignment=ft.Alignment.CENTER,
            title=self.title or "KTV Player",
            controls=self._build_controls(),
            on_load=lambda e: self._hide_overlay(),
            on_duration_change=self._on_duration_change,
            on_position_change=self._on_pos_change,
            on_error=self._on_error,
            on_complete=self._on_complete,
            on_enter_fullscreen=self._on_enter_fullscreen,
            on_exit_fullscreen=self._on_exit_fullscreen,
        )

        self.controls = [
            ft.Container(expand=True, bgcolor=ft.Colors.BLACK),
            self.video,
            self.overlay,
        ]

    # --- Controls ---

    def did_mount(self):
        super().did_mount()
        # The toast chip was created by build_player_controls() in __init__
        register_fullscreen_toast(self.toast_chip, self.toast_text)
        self._setup_resize_listener()
        self._update_title_width()

    def will_unmount(self):
        super().will_unmount()
        self._remove_resize_listener()
        unregister_fullscreen_toast()
        self._cancel_watchdog()
        self._disable_auto_pip()
        # Save position if not already saved
        if self.source_url and self._last_duration > 0 and self._last_position > 3:
            pos_sec = self._last_position
            if pos_sec >= (self._last_duration - 5):
                pos_sec = 0.0
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    db_manager.update_history_position(
                        self.source_url, pos_sec, self._last_duration
                    )
                )
            except RuntimeError:
                pass

    @property
    def safe_page(self):
        if hasattr(self, "_mock_page") and self._mock_page is not None:
            return self._mock_page
        try:
            return self.page
        except Exception:
            return None

    def _setup_resize_listener(self):
        page = self.safe_page
        if not page:
            return
        self._previous_on_resize = getattr(page, "on_resize", None)

        def _on_page_resize(e):
            self._update_title_width()
            if self._previous_on_resize:
                try:
                    res = self._previous_on_resize(e)
                    if hasattr(res, "__await__"):
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                except Exception:
                    pass

        page.on_resize = _on_page_resize

    def _remove_resize_listener(self):
        page = self.safe_page
        if page and hasattr(self, "_previous_on_resize"):
            page.on_resize = self._previous_on_resize
            del self._previous_on_resize

    # --- Android PiP ---

    def _arm_auto_pip(self):
        """Arm auto-PiP once video is actually playing. Modern auto-PiP:
        Android 12+ enters PiP on swipe-home natively (setAutoEnterEnabled);
        Android 8–11 falls back to entering PiP when the lifecycle reports
        the app is actually leaving the screen."""
        if not self.pip_available or self._pip_active:
            return
        self._pip_active = True
        from services import pip_service

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        loop.create_task(asyncio.to_thread(pip_service.set_auto_pip, True))

        # Android 8-11 fallback: hook lifecycle 'hidden' (only fires when the
        # app is really leaving the screen — not for the notification shade)
        page = self.safe_page
        if page and pip_service.api_level() < 31:
            previous = page.on_app_lifecycle_state_change
            self._pip_lifecycle_previous = previous

            def _on_lifecycle(e):
                if getattr(e, "data", None) == "hidden" and self._pip_active:
                    loop.create_task(asyncio.to_thread(pip_service.enter_pip))
                if previous is not None:
                    result = previous(e)
                    if hasattr(result, "__await__"):
                        loop.create_task(result)

            page.on_app_lifecycle_state_change = _on_lifecycle

    def _disarm_auto_pip(self):
        """Disarm auto-PiP: playback ended, errored out, or the player is
        closing. Fire-and-forget so it can never block app shutdown."""
        self._pip_active = False
        if not self.pip_available:
            return
        from services import pip_service

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(asyncio.to_thread(pip_service.set_auto_pip, False))
        except RuntimeError:
            pass

        page = self.safe_page
        if hasattr(self, "_pip_lifecycle_previous") and page:
            page.on_app_lifecycle_state_change = self._pip_lifecycle_previous
            del self._pip_lifecycle_previous

    def _disable_auto_pip(self):
        self._disarm_auto_pip()

        # Sync stop: clear playlist + update() queues a platform channel
        # message that stops native playback immediately. No await needed.
        if self.video and not self._is_closing:
            self._is_closing = True
            try:
                self.video.playlist = []
                self.video.update()
            except Exception:
                pass

    async def enter_pip_mode(self):
        """User-triggered PiP (from control bar icon)."""
        if not self.pip_available:
            return
        from services import pip_service

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, pip_service.enter_pip)
        except Exception as ex:
            logger.debug("Entering PiP failed: %s", ex)

    def _update_title_width(self):
        """Dynamically update title width on window resize, rotation, or fullscreen."""
        if not hasattr(self, "title_container"):
            return
        page = self.safe_page
        if not page:
            return
        width = getattr(page, "width", None)
        if width is None or width <= 0:
            return
        # 48px back button + 32px horizontal margins + 20px padding = 100px
        new_width = max(80, int(width) - 100)
        if self.title_container.width != new_width:
            self.title_container.width = new_width
            try:
                self.title_container.update()
            except Exception:
                pass

    async def _on_enter_fullscreen(self, e):
        """Track fullscreen transition for notifications and update width."""
        set_fullscreen_toast_active(True)
        await self._refresh_title_width_after_transition()

    async def _on_exit_fullscreen(self, e):
        """Track exiting fullscreen and update width."""
        set_fullscreen_toast_active(False)
        await self._refresh_title_width_after_transition()

    async def _refresh_title_width_after_transition(self):
        """Re-apply the title width while a fullscreen/rotation transition
        settles. page.width lags behind the fullscreen route push (the WM
        animation and Flutter metrics land later), and on Android entering
        fullscreen does not resize the window at all — so a single read races
        the new size: a long title stayed truncated after entering fullscreen
        (and an un-truncated one overflowed after exiting). Each apply is a
        no-op unless the computed width actually changed."""
        for delay in (0.2, 0.4, 0.6, 0.8, 0.8):
            await asyncio.sleep(delay)
            if self._is_closing or not self.page:
                return
            self._update_title_width()

    def _build_controls(self) -> fv.AdaptiveVideoControls:
        from components.player.controls import build_player_controls

        return build_player_controls(self)

    async def _pick_subtitles(self):
        from components.player.handlers import pick_subtitles

        await pick_subtitles(self)

    async def _take_screenshot(self):
        import os

        from utils.notifications import notify, notify_warning

        try:
            fmt = getattr(self, "snapshot_format", "image/png")
            inc_subs = getattr(self, "include_subtitles_in_snapshot", True)
            img_bytes = await self.video.take_screenshot(
                format=fmt,
                include_libass_subtitles=inc_subs,
            )
            if img_bytes:
                # Save to public Pictures/KTVPlayer directory on mobile/desktop
                if os.path.exists("/storage/emulated/0"):
                    pictures_dir = "/storage/emulated/0/Pictures/KTVPlayer"
                else:
                    user_home = os.path.expanduser("~")
                    pictures_dir = os.path.join(user_home, "Pictures", "KTVPlayer")

                os.makedirs(pictures_dir, exist_ok=True)

                import datetime
                import re

                raw_title = self.title or "KTV_Player"
                safe_title = re.sub(r"[^\w\s-]", "", raw_title).strip()
                safe_title = re.sub(r"[-\s]+", "_", safe_title) or "KTV_Player"
                timestamp = datetime.datetime.now(tz=datetime.UTC).strftime(
                    "%Y-%m-%d_%H-%M-%S"
                )

                ext = "jpg" if fmt == "image/jpeg" else "png"
                filename = f"{safe_title}_{timestamp}.{ext}"
                filepath = os.path.join(pictures_dir, filename)

                def _write_and_scan():
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)

                    # Scan file so Android Gallery / Google Photos indexes it immediately
                    try:
                        from jnius import autoclass  # type: ignore[import-not-found]

                        candidate_classes = [
                            os.getenv("MAIN_ACTIVITY_HOST_CLASS_NAME"),
                            "ng.kiri.ktvplayer.MainActivity",
                            "net.flet.MainActivity",
                            "com.flet.flet_android.MainActivity",
                        ]
                        activity = None
                        for cls_name in candidate_classes:
                            if not cls_name:
                                continue
                            try:
                                host = autoclass(cls_name)
                                activity = getattr(host, "mActivity", None) or getattr(
                                    host, "mCurrentActivity", None
                                )
                                if activity:
                                    break
                            except Exception as ex:
                                logger.debug(
                                    "Candidate activity %s unavailable for MediaScanner: %s",
                                    cls_name,
                                    ex,
                                )

                        if activity:
                            MediaScannerConnection = autoclass(
                                "android.media.MediaScannerConnection"
                            )
                            MediaScannerConnection.scanFile(
                                activity, [filepath], None, None
                            )
                    except Exception as ex:
                        logger.debug("MediaScannerConnection scan failed: %s", ex)

                await asyncio.to_thread(_write_and_scan)

                notify(f"📸 Snapshot saved to Pictures/KTVPlayer: {filename}")
            else:
                notify_warning("Unable to capture video snapshot.")
        except Exception as ex:
            logger.warning("Screenshot capture failed: %s", ex)

    async def _open_player_settings(self):
        from components.player.handlers import open_player_settings

        await open_player_settings(self)

    # --- Playback ---

    async def start_playback(self):
        logger.info(
            "Initializing playback: title='%s', resource='%s', headers=%s",
            self.title,
            self.resource,
            self.http_headers,
        )
        self._reconnect_count = 0
        # Go Back is available from the very first moment — the player must
        # never be a dead end, not even during the pre-roll ad.
        self._show_progress("Loading stream...")

        # Show interstitial ad before playback, unless player was already closed
        if self.ad_service and not self._is_closing:
            try:
                await asyncio.wait_for(
                    self.ad_service.show_interstitial(),
                    timeout=20.0,
                )
            except TimeoutError:
                logger.warning("Ad timed out during playback start")
            except Exception as ex:
                logger.warning("Ad skipped due to error: %s", ex)

        if self._is_closing:
            logger.info("Playback cancelled — player closed during ad")
            return

        # Resolve YouTube URLs to direct streams (no yt-dlp binary needed).
        # VOD resolves via InnerTube; lives are best-effort — on failure the
        # original URL is kept, and desktop mpv still falls back to yt-dlp.
        if is_youtube_url(self.resource):
            self._show_progress("Resolving YouTube stream...")
            resolved = None
            try:
                from services.youtube_resolver import resolve_youtube_url

                resolved = await asyncio.wait_for(
                    resolve_youtube_url(self.resource), timeout=25.0
                )
            except Exception as ex:
                logger.warning("YouTube resolution failed: %s", ex)
            if resolved and resolved != self.resource:
                logger.info("YouTube resolved to direct stream")
                self.resource = resolved
                self._original_resource = resolved
                # Probe quality/audio on the resolved manifest. source_url
                # MUST stay the original URL: history entries (and their
                # saved positions) are keyed by it — re-keying to the
                # resolved manifest URL makes update_history_position a
                # no-op, silently losing resume positions.
                self.source_proxied = False

        try:
            self.video.playlist = [
                fv.VideoMedia(self.resource, http_headers=self.http_headers),
            ]
            self.video.update()
            await self.video.play()
            self._start_watchdog()
            playing = await self.video.is_playing()
            if playing:
                logger.info("Stream playback started successfully for '%s'", self.title)
                self._hide_overlay()
                # Auto-PiP is armed only now that video is actually
                # playing — mounting the player view is not enough
                # (error/retry overlays used to trigger PiP too).
                self._arm_auto_pip()
        except Exception:
            logger.exception("start_playback error")
            self._show_final_error()

    async def _cycle_speed(self):
        from components.player.handlers import cycle_speed

        await cycle_speed(self)

    def _on_duration_change(self, e: ft.ControlEvent | None = None):
        if not self._overlay_hidden:
            self._hide_overlay()
        if e and hasattr(e, "data") and e.data:
            try:
                val = float(e.data)
                if val > 1_000_000:
                    self._last_duration = val / 1_000_000.0
                elif val > 1_000:
                    self._last_duration = val / 1_000.0
                elif val > 0:
                    self._last_duration = val
            except Exception:
                pass
        self._check_and_trigger_seek()

    def _on_pos_change(self, e: ft.ControlEvent | None = None):
        if not self._overlay_hidden:
            self._hide_overlay()
        if e and hasattr(e, "data") and e.data:
            try:
                val = float(e.data)
                if val > 1_000_000:
                    self._last_position = val / 1_000_000.0
                elif val > 1_000:
                    self._last_position = val / 1_000.0
                elif val > 0:
                    self._last_position = val
            except Exception:
                pass
        self._check_and_trigger_seek()

    def _check_and_trigger_seek(self):
        # After media is ready / first tick, consume any pending one-shot seek target —
        # either the initial resume position loaded from history, or a position captured
        # before a quality/audio swap.
        target = getattr(self, "_pending_seek", None)
        if target is None:
            target = getattr(self, "_initial_resume_position", None)
        if target and target > 3:
            self._pending_seek = None
            self._initial_resume_position = None
            try:
                if self.page:
                    self.page.run_task(self._deferred_seek, target)
            except Exception:
                pass

    async def _deferred_seek(self, seconds: float) -> None:
        try:
            # Poll readiness: mpv discards seek commands sent while the
            # demuxer is still opening network playlists / media tracks.
            for _ in range(40):  # up to 4.0s wait
                if self._is_closing or not self.video:
                    return
                try:
                    dur = await self.video.get_duration()
                    if dur and dur.in_seconds > 0:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.1)

            if self._is_closing or not self.video:
                return

            await asyncio.sleep(0.05)
            await self.video.seek(ft.Duration(seconds=int(seconds)))
            self._last_position = seconds
            logger.info("Deferred seek succeeded to %s seconds", seconds)
            from utils.notifications import notify

            mins, secs = divmod(int(seconds), 60)
            hrs, mins = divmod(mins, 60)
            time_str = (
                f"{hrs:02d}:{mins:02d}:{secs:02d}"
                if hrs > 0
                else f"{mins:02d}:{secs:02d}"
            )
            notify(f"⏱️ Resumed from {time_str}")
        except Exception as ex:
            logger.debug("Deferred seek failed: %s", ex)

    def _hide_overlay(self):
        if not self._overlay_hidden:
            self._overlay_hidden = True
            self._cancel_watchdog()
            self.overlay.visible = False
            try:
                self.update()
            except Exception as ex:
                logger.debug(
                    "Failed to hide overlay (component might be unmounted): %s", ex
                )
            # First successful playback: probe the stream once for quality /
            # audio options so the button can appear.
            if not getattr(self, "_options_probed", False):
                self._options_probed = True
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._probe_stream_options())
                except RuntimeError:
                    pass

    def _enable_tap_to_close(self):
        self.overlay.on_click = lambda _: self.page.run_task(self.handle_close)

    def _safe_update(self):
        try:
            self.update()
        except Exception:
            pass

    def _show_progress(self, message: str, show_back: bool = True):
        """Overlay state for loading/reconnecting: spinner + status, with Go
        Back always available (visible button + tap-to-close) so a stalling
        stream is never a dead end."""
        self._overlay_hidden = False
        self.status_text.value = message
        self.loading_ring.visible = True
        self.error_actions_row.visible = True
        self.retry_btn.visible = False
        self.back_error_btn.visible = show_back
        self.overlay.visible = True
        self._enable_tap_to_close()
        self._safe_update()

    # --- Quality / audio-track switching (HLS via proxy) ---

    def _resource_url_for(self, variant: int | None, audio: str | None) -> str:
        """Rebuild the playback URL for a (variant, audio) pinning choice."""
        if (
            self.hls_proxy
            and self.source_url
            and (variant is not None or audio is not None or self.source_proxied)
        ):
            try:
                return self.hls_proxy.get_proxy_url(
                    self.source_url,
                    referer=self.source_referer,
                    headers=self.source_headers,
                    variant=variant,
                    audio=audio,
                )
            except Exception:
                pass
        return self._original_resource

    @property
    def can_switch_quality(self) -> bool:
        return bool(self.hls_proxy) and self.source_url.startswith(
            ("http://", "https://")
        )

    async def list_variants(self) -> list[dict]:
        """HLS master variants (cached). Empty for media playlists/non-HLS."""
        if self._variants_cache is not None:
            return self._variants_cache
        if not self.can_switch_quality:
            return []
        try:
            variants = await asyncio.wait_for(
                self.hls_proxy.fetch_variants(
                    self.source_url, headers=self.source_headers
                ),
                timeout=8.0,
            )
        except Exception:
            variants = []
        self._variants_cache = variants or []
        return self._variants_cache

    async def list_audio_tracks(self) -> list[dict]:
        """External HLS audio renditions (cached). Muxed audio is not
        switchable via manifest rewriting."""
        if self._audio_tracks_cache is not None:
            return self._audio_tracks_cache
        if not self.can_switch_quality:
            return []
        try:
            tracks = await asyncio.wait_for(
                self.hls_proxy.fetch_audio_tracks(
                    self.source_url, headers=self.source_headers
                ),
                timeout=8.0,
            )
        except Exception:
            tracks = []
        self._audio_tracks_cache = tracks or []
        return self._audio_tracks_cache

    async def _swap_media(self, message: str) -> None:
        """Restart playback on the currently pinned resource, restoring the
        position for seekable streams (live streams stay at the live edge)."""
        if self._is_closing or not self.video:
            return
        new_url = self._resource_url_for(self._current_variant, self._current_audio)
        position = None
        duration = None
        try:
            pos_task = asyncio.create_task(self.video.get_current_position())
            position = await asyncio.wait_for(pos_task, timeout=0.8)
        except Exception:
            pass
        try:
            dur_task = asyncio.create_task(self.video.get_duration())
            duration = await asyncio.wait_for(dur_task, timeout=0.8)
        except Exception:
            pass

        pos_sec = (
            position.in_seconds
            if (position and position.in_seconds > 0)
            else self._last_position
        )
        dur_sec = (
            duration.in_seconds
            if (duration and duration.in_seconds > 0)
            else self._last_duration
        )
        if dur_sec > 0:
            self._last_duration = dur_sec

        self.resource = new_url
        self._show_progress(message)
        # Restore position for finite streams (VOD duration > 0)
        if dur_sec > 0 and pos_sec > 3:
            self._pending_seek = pos_sec

        try:
            self.video.playlist = [
                fv.VideoMedia(new_url, http_headers=self.http_headers),
            ]
            self.video.update()
            await self.video.play()
            self._start_watchdog()
        except Exception as ex:
            logger.error("Stream switch failed: %s", ex)
            self._show_final_error("Switch failed. Stream may be offline.")

    async def apply_variant(self, index: int | None) -> None:
        """Pin a quality variant (None = Auto)."""
        self._current_variant = index
        self._refresh_quality_label()
        await self._swap_media(
            "Auto quality" if index is None else "Switching quality..."
        )

    async def apply_audio(self, name: str | None) -> None:
        """Pin an audio rendition (None = manifest default)."""
        self._current_audio = name
        self._refresh_audio_label()
        await self._swap_media(
            "Default audio" if name is None else "Switching audio..."
        )

    def _refresh_quality_label(self) -> None:
        """Sync the quality button with the current pinning."""
        text = getattr(self, "quality_text", None)
        btn = getattr(self, "quality_btn", None)
        if not text or not btn:
            return
        if self._current_variant is None:
            text.value = "Auto"
        else:
            current = next(
                (
                    v
                    for v in (self._variants_cache or [])
                    if v.get("index") == self._current_variant
                ),
                None,
            )
            text.value = (
                _short_variant_label(current)
                if current
                else f"V{self._current_variant + 1}"
            )
        try:
            btn.update()
        except Exception:
            pass

    def _refresh_audio_label(self) -> None:
        """Sync the audio button with the current pinning."""
        text = getattr(self, "audio_text", None)
        btn = getattr(self, "audio_btn", None)
        if not text or not btn:
            return
        if self._current_audio is None:
            text.value = "Default"
        else:
            text.value = self._current_audio
        try:
            btn.update()
        except Exception:
            pass

    async def _probe_stream_options(self) -> None:
        """Fetch variants/audio once playback is running; reveal the quality and audio
        buttons in bottom bar only when the stream actually has options to pick."""
        if not self.can_switch_quality or self._is_closing:
            return
        variants = await self.list_variants()
        tracks = await self.list_audio_tracks() if variants else []
        if self._is_closing:
            return

        # Quality button
        q_btn = getattr(self, "quality_btn", None)
        q_row = getattr(self, "quality_row", None)
        if q_btn is not None and q_row is not None and len(variants) > 1:
            q_btn.content = q_row
            q_btn.padding = ft.Padding(6, 3, 6, 3)
            self._refresh_quality_label()
            try:
                q_btn.update()
            except Exception:
                pass

        # Audio button
        a_btn = getattr(self, "audio_btn", None)
        a_row = getattr(self, "audio_row", None)
        if a_btn is not None and a_row is not None and len(tracks) >= 2:
            a_btn.content = a_row
            a_btn.padding = ft.Padding(6, 3, 6, 3)
            self._refresh_audio_label()
            try:
                a_btn.update()
            except Exception:
                pass

    async def open_quality_picker(self) -> None:
        """Open the player settings dialog with Stream Quality & Audio options."""
        from components.player.handlers import open_player_settings

        await open_player_settings(self)

    async def enter_pip(self) -> bool:
        """Enter Android Picture-in-Picture now (button action)."""
        try:
            from services.pip_service import enter_pip

            return await asyncio.to_thread(enter_pip)
        except Exception:
            return False

    # --- Watchdog ---

    def _start_watchdog(self, timeout: float | None = None):
        """Guarantee every loading/reconnecting state resolves: if no load,
        position or error event arrives within `timeout`, swap the spinner
        for the retry/back UI instead of spinning forever."""
        self._cancel_watchdog()
        secs = _WATCHDOG_SECONDS if timeout is None else timeout

        async def _watchdog():
            await asyncio.sleep(secs)
            if self._is_closing or self._is_final_error or self._overlay_hidden:
                return
            logger.warning(
                "Playback watchdog fired after %.1fs — no load/position/error",
                secs,
            )
            self._show_final_error("Stream is not responding. Retry or go back.")

        try:
            loop = asyncio.get_running_loop()
            self._watchdog_task = loop.create_task(_watchdog())
        except RuntimeError:
            pass

    def _cancel_watchdog(self):
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        self._watchdog_task = None

    # --- Error handling & retry ---

    def _on_error(self, e: ft.ControlEvent):
        err_msg = str(e.data) if hasattr(e, "data") and e.data else str(e)
        logger.debug("on_error: %s", err_msg)
        if self._is_closing:
            return
        if "Cannot seek" in err_msg or "force-seekable" in err_msg:
            return
        if self._is_final_error:
            return

        self._show_final_error(
            "Unable to load stream. Please check connection or retry."
        )

    def _show_final_error(self, message: str = "Playback failed."):
        self._cancel_watchdog()
        self._is_final_error = True
        # Playback is dead — minimize must NOT trigger PiP anymore.
        self._disarm_auto_pip()
        self._overlay_hidden = False
        self.status_text.value = message
        self.loading_ring.visible = False
        self.error_actions_row.visible = True
        self.retry_btn.visible = True
        self.back_error_btn.visible = True
        self.overlay.visible = True
        self._enable_tap_to_close()
        self._safe_update()

    async def _manual_retry(self):
        if self._is_closing:
            return
        self._is_final_error = False
        self._reconnect_count = 0
        self._show_progress("Reconnecting stream...")

        try:
            if self.video:
                self.video.playlist = [
                    fv.VideoMedia(self.resource, http_headers=self.http_headers),
                ]
                self.video.update()
                await self.video.play()
        except Exception as ex:
            logger.error("Manual retry playback failed: %s", ex)
            self._show_final_error("Retry failed. Stream may be offline.")
            return
        self._start_watchdog()
        self._arm_auto_pip()

    async def _save_current_position(self) -> None:
        """Capture and save playback position on player close for VOD streams."""
        try:
            if not self.video or not self.source_url:
                return
            pos = None
            dur = None
            try:
                pos_task = asyncio.create_task(self.video.get_current_position())
                pos = await asyncio.wait_for(pos_task, timeout=0.8)
            except Exception:
                pos = None
            try:
                dur_task = asyncio.create_task(self.video.get_duration())
                dur = await asyncio.wait_for(dur_task, timeout=0.8)
            except Exception:
                dur = None

            pos_sec = pos.in_seconds if pos else self._last_position
            dur_sec = dur.in_seconds if dur else self._last_duration

            # Only save for finite/VOD streams (duration > 0) with meaningful progress (> 3s)
            if dur_sec > 0 and pos_sec > 3:
                # If near the end (within 5s of completion), reset position to 0
                if pos_sec >= (dur_sec - 5):
                    pos_sec = 0.0
                await db_manager.update_history_position(
                    self.source_url, pos_sec, dur_sec
                )
        except Exception as ex:
            logger.debug("Saving playback position failed: %s", ex)

    def _on_complete(self, e: ft.ControlEvent):
        # Video finished — nothing is playing, so PiP auto-enter is disarmed.
        self._disarm_auto_pip()
        if self.source_url:
            with contextlib.suppress(Exception):
                loop = asyncio.get_running_loop()
                loop.create_task(
                    db_manager.update_history_position(
                        self.source_url, 0.0, self._last_duration
                    )
                )
        from components.player.handlers import handle_stream_complete

        handle_stream_complete(self, e)

    # --- Close ---

    async def handle_close(self, e: ft.ControlEvent | None = None):
        if self._is_closing:
            return
        self._is_closing = True
        self._is_final_error = True
        self._cancel_watchdog()
        self._disarm_auto_pip()
        await self._save_current_position()
        try:
            if self.video:
                # 1. Async stop first — proper player cleanup
                with contextlib.suppress(Exception):
                    await self.video.stop()
                # 2. Clear playlist + update() — sync final cleanup
                self.video.playlist = []
                self.video.update()
        except Exception as ex:
            logger.debug("Ignored error while stopping video on close: %s", ex)

    async def _on_back(self, e: ft.ControlEvent | None = None):
        await self.handle_close()
        if self.on_close:
            try:
                result = self.on_close()
                if hasattr(result, "__await__"):
                    await result
            except Exception as ex:
                logger.error("Error executing on_close callback: %s", ex)
