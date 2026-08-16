import asyncio
import contextlib
import logging
from collections.abc import Callable
from typing import Any

import flet as ft
import flet_video as fv

from core.theme import AppColors
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
    ):
        super().__init__()
        self.resource = resource
        self.on_close = on_close
        self.title = title
        self.http_headers = http_headers or {}
        self.ad_service = ad_service
        # Deep-link plays (ktv://) hide the in-player favorite star
        self.show_favorite_button = show_favorite
        self.expand = True

        self._retry_count = 0
        self._reconnect_count = 0
        self._is_final_error = False
        self._is_closing = False
        self._was_closed_during_ad = False
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
                hardware_decoding_api="mediacodec",
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
        self._update_title_width()
        # The toast chip was created by build_player_controls() in __init__
        register_fullscreen_toast(self.toast_chip, self.toast_text)

    def will_unmount(self):
        super().will_unmount()
        unregister_fullscreen_toast()
        self._cancel_watchdog()
        # Sync stop: clear playlist + update() queues a platform channel
        # message that stops native playback immediately. No await needed.
        if self.video and not self._is_closing:
            self._is_closing = True
            try:
                self.video.playlist = []
                self.video.update()
            except Exception:
                pass

    def _update_title_width(self):
        if not hasattr(self, "title_container") or not self.page:
            return
        width = self.page.width
        if width is None or width <= 0:
            return
        # 48px back button + 32px horizontal margins = 80px
        new_width = max(100, int(width) - 80)
        if self.title_container.width != new_width:
            self.title_container.width = new_width
            try:
                self.title_container.update()
            except Exception:
                pass

    async def _on_enter_fullscreen(self, e):
        """Fullscreen covers the whole Flet page tree (SnackBar included),
        so notifications must route to the in-controls toast chip."""
        set_fullscreen_toast_active(True)
        await self._refresh_title_width_after_transition()

    async def _on_exit_fullscreen(self, e):
        """Back to normal rendering — SnackBar works again."""
        set_fullscreen_toast_active(False)
        await self._refresh_title_width_after_transition()

    async def _refresh_title_width_after_transition(self):
        """Re-apply the title width while a fullscreen/rotation transition
        settles. Page has NO resize event in Flet 0.86, and page.width lags
        behind the fullscreen route push (the WM animation and Flutter
        metrics land later), so a single delayed read races the new size —
        a long title stayed truncated after entering fullscreen (and an
        un-truncated one overflowed after exiting). Each apply is a no-op
        unless the computed width actually changed."""
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
        except Exception:
            logger.exception("start_playback error")
            self._show_final_error()

    async def _cycle_speed(self):
        from components.player.handlers import cycle_speed

        await cycle_speed(self)

    def _on_pos_change(self, e: ft.ControlEvent | None = None):
        if not self._overlay_hidden:
            self._hide_overlay()

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

    def _on_complete(self, e: ft.ControlEvent):
        from components.player.handlers import handle_stream_complete

        handle_stream_complete(self, e)

    # --- Close ---

    async def handle_close(self, e: ft.ControlEvent | None = None):
        if self._is_closing:
            return
        self._is_closing = True
        self._is_final_error = True
        self._cancel_watchdog()
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
