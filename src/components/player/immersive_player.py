import asyncio
import contextlib
import logging
import re
from collections.abc import Callable

import flet as ft
import flet_video as fv

from core.constants import STREAM_RECONNECT_MAX, STREAM_RETRY_DELAY, STREAM_RETRY_MAX
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
        playback_rate: float = 1.0,
        muted: bool = False,
        fill_color: ft.ColorValue = ft.Colors.BLACK,
        fit: ft.BoxFit = ft.BoxFit.CONTAIN,
        alignment: ft.Alignment = ft.Alignment.CENTER,
        wakelock: bool = True,
        pause_upon_entering_background_mode: bool = True,
        resume_upon_entering_foreground_mode: bool = True,
        http_headers: dict | None = None,
        subtitle_track: fv.VideoSubtitleTrack | None = None,
    ):
        super().__init__()
        self.resource = resource
        self.on_close = on_close
        self.title = title
        self.http_headers = http_headers or {}
        self.expand = True

        self._retry_count = 0
        self._max_retries = STREAM_RETRY_MAX
        self._is_final_error = False
        self._reconnect_count = 0
        self._max_reconnects = STREAM_RECONNECT_MAX
        self._is_closing = False
        self._previous_keyboard_handler = None

        self.status_text = ft.Text(
            "Loading stream...",
            size=16,
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_500,
            text_align=ft.TextAlign.CENTER,
        )
        self.loading_ring = ft.ProgressRing(
            width=48, height=48, stroke_width=4, color=AppColors.PRIMARY
        )

        self.overlay = ft.Container(
            expand=True,
            bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.BLACK),
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    self.loading_ring,
                    ft.Container(height=20),
                    self.status_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )

        self._overlay_hidden = False

        self._speed_idx = 1
        self.speed_text = ft.Text("1.0x", size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600)

        self._initial_playlist = [
            fv.VideoMedia(self.resource, http_headers=self.http_headers)
        ]

        self.video = fv.Video(
            autoplay=autoplay,
            expand=True,
            volume=volume,
            playback_rate=playback_rate,
            muted=muted,
            wakelock=wakelock,
            filter_quality=ft.FilterQuality.LOW,
            pause_upon_entering_background_mode=pause_upon_entering_background_mode,
            resume_upon_entering_foreground_mode=resume_upon_entering_foreground_mode,
            subtitle_track=subtitle_track,
            subtitle_configuration=fv.VideoSubtitleConfiguration(
                text_align=ft.TextAlign.CENTER,
                text_style=ft.TextStyle(
                    size=20,
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.W_600,
                    bgcolor=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
                ),
            ),
            configuration=fv.VideoConfiguration(
                hardware_decoding_api="mediacodec",
                mpv_properties={
                    "cache": "yes",
                    "cache-secs": "5",
                    "demuxer-max-bytes": "50M",
                    "demuxer-max-back-bytes": "10M",
                },
            ),
            fill_color=fill_color,
            fit=fit,
            alignment=alignment,
            title=self.title or "KTV Player",
            controls=self._build_controls(),
            on_load=self._on_load,
            on_error=self._on_error,
            on_complete=self._on_complete,
            on_position_change=self._on_position_change,
            on_duration_change=self._on_duration_change,
            on_track_change=self._on_track_change,
            on_enter_fullscreen=self._on_enter_fullscreen,
            on_exit_fullscreen=self._on_exit_fullscreen,
        )

        # Removed the buggy Stack elements (back_btn and title_bar)
        # because they are now rendered safely inside the video controls!
        self.controls = [
            ft.Container(expand=True, bgcolor=ft.Colors.BLACK),
            self.video,
            self.overlay,
        ]

    def did_mount(self):
        self._previous_keyboard_handler = self.page.on_keyboard_event
        self.page.on_keyboard_event = self._handle_player_keyboard

    def will_unmount(self):
        if self._previous_keyboard_handler is not None:
            self.page.on_keyboard_event = self._previous_keyboard_handler

    def _handle_player_keyboard(self, e: ft.KeyboardEvent):
        if e.key in ("Escape", "Back", "BrowserBack"):
            self.page.run_task(self._on_back)
        elif self._previous_keyboard_handler:
            self._previous_keyboard_handler(e)

    def _build_controls(self):
        # We exclusively use MaterialDesktopVideoControls because it perfectly handles 
        # injecting custom top_button_bar items so they respond reliably to touch.
        return fv.MaterialDesktopVideoControls(
            visible_on_mount=True,
            display_seek_bar=True,
            modify_volume_on_scroll=True,
            toggle_fullscreen_on_double_press=True,
            play_and_pause_on_tap=False,
            hide_mouse_on_controls_removal=True,
            primary_button_bar=[
                fv.VideoSkipPreviousButton(icon_color=ft.Colors.WHITE),
                fv.VideoPlayOrPauseButton(icon_size=36, icon_color=ft.Colors.WHITE),
                fv.VideoSkipNextButton(icon_color=ft.Colors.WHITE),
            ],
            top_button_bar=[
                # Inject Back Button and Title NATIVELY into the player UI
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                    icon_color=ft.Colors.WHITE,
                    tooltip="Back",
                    on_click=lambda e: self.page.run_task(self._on_back, e),
                ),
                ft.Text(
                    self.title or "Now Playing", 
                    color=ft.Colors.WHITE, 
                    weight=ft.FontWeight.W_500,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                fv.VideoSpacer(),
                self._build_screenshot_btn(),
                fv.VideoFullscreenButton(icon_color=ft.Colors.WHITE),
            ],
            bottom_button_bar=[
                fv.VideoVolumeButton(slider_width=80, icon_color=ft.Colors.WHITE),
                fv.VideoSpacer(),
                fv.VideoPositionIndicator(
                    text_style=ft.TextStyle(size=12, color=ft.Colors.WHITE),
                ),
                fv.VideoSpacer(),
                self._build_speed_btn(),
            ],
            seek_bar_position_color=AppColors.PRIMARY,
            seek_bar_buffer_color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
            seek_bar_hover_height=8,
            volume_bar_active_color=AppColors.PRIMARY,
            controls_hover_duration=ft.Duration(seconds=3),
        )

    def _build_screenshot_btn(self):
        btn = ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.CAMERA_ALT,
                icon_color=ft.Colors.WHITE,
                icon_size=20,
                tooltip="Screenshot",
            ),
            on_click=lambda e: self.page.run_task(self._handle_screenshot),
        )
        btn.tab_index = 0
        return btn

    def _build_speed_btn(self):
        btn = ft.Container(
            content=self.speed_text,
            padding=ft.Padding(8, 4, 8, 4),
            border_radius=4,
            ink=True,
            on_click=lambda e: self.page.run_task(self._cycle_speed),
        )
        btn.tab_index = 0
        return btn

    async def _handle_screenshot(self):
        try:
            image = await self.take_screenshot("image/jpeg")
            if image:
                snack = ft.SnackBar(
                    ft.Text(f"Screenshot captured ({len(image)} bytes)"),
                    bgcolor=AppColors.SUCCESS,
                )
                self.page.show_snack_bar(snack)
            else:
                snack = ft.SnackBar(
                    ft.Text("No video frame available yet"),
                    bgcolor=AppColors.WARNING,
                )
                self.page.show_snack_bar(snack)
        except Exception as ex:
            snack = ft.SnackBar(
                ft.Text(f"Screenshot failed: {ex}"),
                bgcolor=AppColors.ERROR,
            )
            self.page.show_snack_bar(snack)

    async def start_playback(self):
        logger.debug("start_playback resource=%s", self.resource[:60])
        self._reconnect_count = 0
        try:
            self.video.playlist = self._initial_playlist
            self.video.update()
            await self.video.play()
            playing = await self.video.is_playing()
            if playing:
                self._hide_overlay()
            logger.debug("start_playback OK is_playing=%s", playing)
        except Exception as ex:
            logger.exception("start_playback error: %s", ex)
            self._show_final_error()

    async def _cycle_speed(self):
        speeds = [0.25, 0.5, 1.0, 1.25, 1.5, 2.0]
        self._speed_idx = (self._speed_idx + 1) % len(speeds)
        new_speed = speeds[self._speed_idx]
        await self.set_playback_rate(new_speed)

    def _on_load(self, e):
        logger.debug("on_load fired, data=%s", e.data)

    def _hide_overlay(self):
        if not self._overlay_hidden:
            self._overlay_hidden = True
            self.overlay.visible = False
            with contextlib.suppress(Exception):
                self.update()

    def _on_position_change(self, e):
        self._hide_overlay()

    def _on_error(self, e):
        err_msg = str(e.data) if hasattr(e, "data") and e.data else str(e)
        logger.debug("on_error fired: %s", err_msg)
        if "Cannot seek" in err_msg or "force-seekable" in err_msg:
            return
        if self._is_final_error:
            return
        self._retry_count += 1
        if self._retry_count <= self._max_retries and self.resource.startswith("http"):
            logger.debug("retry %d/%d", self._retry_count, self._max_retries)
            self.status_text.value = f"Stream error, retrying ({self._retry_count}/{self._max_retries})..."
            self.loading_ring.visible = True
            self.overlay.visible = True
            self.update()
            self.page.run_task(self._retry_playback)
        else:
            logger.debug("showing final error after %d retries", self._retry_count)
            self._show_final_error()

    def _show_final_error(self):
        self._is_final_error = True
        self.status_text.value = "Failed to load. Tap to go back."
        self.loading_ring.visible = False
        self.overlay.visible = True
        self.overlay.on_click = lambda _: self.page.run_task(self.handle_close)
        self.update()

    async def _reconnect_stream(self):
        try:
            if self.video:
                self.video.playlist = [
                    fv.VideoMedia(self.resource, http_headers=self.http_headers)
                ]
                self.overlay.visible = False
                self.update()
        except Exception:
            pass

    async def _retry_playback(self):
        try:
            await asyncio.sleep(STREAM_RETRY_DELAY)
            if self.video and not self._is_final_error:
                self.video.playlist = [
                    fv.VideoMedia(self.resource, http_headers=self.http_headers)
                ]
                await self.play()
                self.overlay.visible = False
                self._retry_count = 0
                self.update()
        except Exception:
            self._show_final_error()

    def _on_complete(self, e):
        if re.match(r"https?://", self.resource):
            if self._reconnect_count < self._max_reconnects:
                self._reconnect_count += 1
                self.page.run_task(self._reconnect_stream)
            else:
                self.status_text.value = "Stream ended. Tap to go back."
                self.loading_ring.visible = False
                self.overlay.visible = True
                self.overlay.on_click = lambda _: self.page.run_task(self.handle_close)
                self.update()

    def _on_duration_change(self, e):
        pass

    def _on_track_change(self, e):
        pass

    def _on_enter_fullscreen(self, e):
        pass

    def _on_exit_fullscreen(self, e):
        pass

    async def handle_close(self, e=None):
        if self._is_closing:
            return
        self._is_closing = True
        try:
            if self.video:
                self.video.playlist = []
                await self.video.stop()
        except Exception:
            pass
        self._is_final_error = True
        self._is_closing = False

    async def _on_back(self, e=None):
        await self.handle_close()
        if self.on_close:
            try:
                result = self.on_close()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass

    async def play(self):
        if self.video and hasattr(self.video, "play"):
            await self.video.play()

    async def pause(self):
        if self.video and hasattr(self.video, "pause"):
            await self.video.pause()

    async def stop(self):
        if self.video and hasattr(self.video, "stop"):
            await self.video.stop()

    async def play_or_pause(self):
        if self.video and hasattr(self.video, "play_or_pause"):
            await self.video.play_or_pause()

    async def seek(self, position: ft.DurationValue):
        if self.video and hasattr(self.video, "seek"):
            await self.video.seek(position)

    async def next(self):
        if self.video and hasattr(self.video, "next"):
            await self.video.next()

    async def previous(self):
        if self.video and hasattr(self.video, "previous"):
            await self.video.previous()

    async def jump_to(self, media_index: int):
        if self.video and hasattr(self.video, "jump_to"):
            await self.video.jump_to(media_index)

    async def is_playing(self) -> bool:
        if self.video and hasattr(self.video, "is_playing"):
            return await self.video.is_playing()
        return False

    async def is_completed(self) -> bool:
        if self.video and hasattr(self.video, "is_completed"):
            return await self.video.is_completed()
        return False

    async def get_current_position(self) -> ft.Duration:
        if self.video and hasattr(self.video, "get_current_position"):
            return await self.video.get_current_position()
        return ft.Duration()

    async def get_duration(self) -> ft.Duration:
        if self.video and hasattr(self.video, "get_duration"):
            return await self.video.get_duration()
        return ft.Duration()

    async def take_screenshot(self, fmt: str = "image/jpeg", include_libass_subtitles: bool = False) -> bytes | None:
        if self.video and hasattr(self.video, "take_screenshot"):
            return await self.video.take_screenshot(format=fmt, include_libass_subtitles=include_libass_subtitles)
        return None

    async def set_volume(self, volume: float):
        if self.video:
            self.video.volume = max(0.0, min(100.0, volume))
            with contextlib.suppress(Exception):
                self.video.update()

    async def set_playback_rate(self, rate: float):
        if self.video:
            self.video.playback_rate = rate
            self.speed_text.value = f"{rate}x"
            try:
                self.video.update()
                self.speed_text.update()
            except Exception:
                pass

    async def set_muted(self, muted: bool):
        if self.video:
            self.video.muted = muted
            with contextlib.suppress(Exception):
                self.video.update()

    async def set_pitch(self, pitch: float):
        if self.video:
            self.video.pitch = pitch
            with contextlib.suppress(Exception):
                self.video.update()