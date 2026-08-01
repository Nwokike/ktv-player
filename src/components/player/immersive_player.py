import asyncio
import logging
from collections.abc import Callable
from typing import Any

import flet as ft
import flet_video as fv

from core.constants import STREAM_RETRY_DELAY, STREAM_RETRY_MAX
from core.theme import AppColors

logger = logging.getLogger(__name__)


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
    ):
        super().__init__()
        self.resource = resource
        self.on_close = on_close
        self.title = title
        self.http_headers = http_headers or {}
        self.ad_service = ad_service
        self.expand = True

        self._retry_count = 0
        self._reconnect_count = 0
        self._is_final_error = False
        self._is_closing = False
        self._was_closed_during_ad = False

        # Overlay
        self.status_text = ft.Text(
            "Loading stream...",
            size=16,
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
        self.overlay = ft.Container(
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.BLACK),
            alignment=ft.Alignment.CENTER,
            on_click=None,  # Will be bound only when tapping to close is allowed
            content=ft.Column(
                [self.loading_ring, ft.Container(height=20), self.status_text],
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

        # Video player
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
        )

        self.controls = [
            ft.Container(expand=True, bgcolor=ft.Colors.BLACK),
            self.video,
            self.overlay,
        ]

    # --- Controls ---

    def _build_controls(self) -> fv.AdaptiveVideoControls:
        from components.player.controls import build_player_controls

        return build_player_controls(self)

    async def _pick_subtitles(self):
        from components.player.handlers import pick_subtitles

        await pick_subtitles(self)

    async def _take_screenshot(self):
        import os
        import time

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

                ext = "jpg" if fmt == "image/jpeg" else "png"
                filename = f"ktv_snap_{int(time.time())}.{ext}"
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
            self.overlay.visible = False
            try:
                self.update()
            except Exception as ex:
                logger.debug(
                    "Failed to hide overlay (component might be unmounted): %s", ex
                )

    def _enable_tap_to_close(self):
        self.overlay.on_click = lambda _: self.page.run_task(self.handle_close)

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

        self._retry_count += 1
        if self._retry_count <= STREAM_RETRY_MAX and self.resource.startswith("http"):
            self.status_text.value = (
                f"Stream error, retrying ({self._retry_count}/{STREAM_RETRY_MAX})..."
            )
            self._overlay_hidden = False
            self.loading_ring.visible = True
            self.overlay.visible = True
            self._enable_tap_to_close()
            self.update()
            self.page.run_task(self._retry_playback)
        else:
            self._show_final_error()

    def _show_final_error(self):
        self._is_final_error = True
        self._overlay_hidden = False
        self.status_text.value = "Failed to load. Tap to go back."
        self.loading_ring.visible = False
        self.overlay.visible = True
        self._enable_tap_to_close()
        self.update()

    async def _retry_playback(self):
        try:
            await asyncio.sleep(STREAM_RETRY_DELAY)

            # Prevent retrying if player was closed during sleep
            if self._is_closing:
                return

            if self.video and not self._is_final_error:
                self.video.playlist = [
                    fv.VideoMedia(self.resource, http_headers=self.http_headers),
                ]
                self.video.update()
                await self.video.play()
        except Exception as ex:
            logger.error("Retry playback failed: %s", ex)
            self._show_final_error()

    def _on_complete(self, e: ft.ControlEvent):
        from components.player.handlers import handle_stream_complete

        handle_stream_complete(self, e)

    # --- Close ---

    async def handle_close(self, e: ft.ControlEvent | None = None):
        if self._is_closing:
            return
        self._is_closing = True
        self._is_final_error = True
        try:
            if self.video:
                self.video.playlist = []
                self.video.update()
                await self.video.stop()
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
