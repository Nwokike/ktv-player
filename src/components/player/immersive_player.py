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
        muted: bool = False,
        http_headers: dict | None = None,
        ad_service=None,
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
        self._previous_keyboard_handler = None

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
            configuration=fv.VideoConfiguration(
                hardware_decoding_api="mediacodec",
                mpv_properties={
                    "cache": "yes",
                    "cache-secs": "5",
                    "demuxer-max-bytes": "50M",
                    "demuxer-max-back-bytes": "10M",
                },
            ),
            fill_color=ft.Colors.BLACK,
            fit=ft.BoxFit.CONTAIN,
            alignment=ft.Alignment.CENTER,
            title=self.title or "KTV Player",
            controls=self._build_controls(),
            on_load=lambda e: logger.debug("on_load: %s", e.data),
            on_error=self._on_error,
            on_complete=self._on_complete,
            on_position_change=lambda e: self._hide_overlay(),
        )

        self.controls = [
            ft.Container(expand=True, bgcolor=ft.Colors.BLACK),
            self.video,
            self.overlay,
        ]

    # --- Lifecycle ---

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

    # --- Controls ---

    def _build_controls(self):
        speed_container = ft.Container(
            content=self.speed_text,
            padding=ft.Padding(8, 4, 8, 4),
            border_radius=4,
            ink=True,
            on_click=lambda e: self.page.run_task(self._cycle_speed),
        )
        speed_container.tab_index = 0

        back_btn = ft.IconButton(
            icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
            icon_color=ft.Colors.WHITE,
            tooltip="Back",
            on_click=lambda e: self.page.run_task(self._on_back, e),
        )
        title_text = ft.Text(
            self.title or "Now Playing",
            color=ft.Colors.WHITE,
            weight=ft.FontWeight.W_500,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        return fv.AdaptiveVideoControls(
            # --- Mobile (touch) ---
            material=fv.MaterialVideoControls(
                visible_on_mount=True,
                display_seek_bar=True,
                seek_on_double_tap=True,
                seek_gesture=True,
                volume_gesture=True,
                brightness_gesture=True,
                speed_up_on_long_press=True,
                speed_up_factor=2.0,
                controls_transition_duration=ft.Duration(milliseconds=300),
                seek_bar_position_color=AppColors.PRIMARY,
                button_bar_button_color=ft.Colors.WHITE,
                top_button_bar_margin=ft.Margin(16, 35, 16, 0),
                top_button_bar=[
                    back_btn,
                    title_text,
                    fv.VideoSpacer(),
                    fv.VideoFullscreenButton(icon_color=ft.Colors.WHITE),
                ],
                bottom_button_bar=[
                    fv.VideoPositionIndicator(
                        text_style=ft.TextStyle(size=12, color=ft.Colors.WHITE),
                    ),
                    fv.VideoSpacer(),
                    speed_container,
                ],
            ),
            # --- Desktop / TV (keyboard + D-pad) ---
            material_desktop=fv.MaterialDesktopVideoControls(
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
                    back_btn,
                    title_text,
                    fv.VideoSpacer(),
                    fv.VideoFullscreenButton(icon_color=ft.Colors.WHITE),
                ],
                bottom_button_bar=[
                    fv.VideoVolumeButton(slider_width=80, icon_color=ft.Colors.WHITE),
                    fv.VideoSpacer(),
                    fv.VideoPositionIndicator(
                        text_style=ft.TextStyle(size=12, color=ft.Colors.WHITE),
                    ),
                    fv.VideoSpacer(),
                    speed_container,
                ],
                seek_bar_position_color=AppColors.PRIMARY,
                seek_bar_buffer_color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
                seek_bar_hover_height=8,
                volume_bar_active_color=AppColors.PRIMARY,
                controls_hover_duration=ft.Duration(seconds=3),
            ),
        )

    # --- Playback ---

    async def start_playback(self):
        logger.debug("start_playback resource=%s", self.resource[:60])
        self._reconnect_count = 0

        # Show interstitial ad before playback, unless player was already closed
        if self.ad_service and not self._is_closing:
            try:
                await asyncio.wait_for(
                    self.ad_service.show_interstitial(),
                    timeout=20.0,
                )
            except (asyncio.TimeoutError, Exception):
                logger.warning("Ad skipped or timed out during playback start")

        if self._is_closing:
            logger.debug("Playback cancelled — player closed during ad")
            return

        try:
            self.video.playlist = [
                fv.VideoMedia(self.resource, http_headers=self.http_headers),
            ]
            self.video.update()
            await self.video.play()
            playing = await self.video.is_playing()
            if playing:
                self._hide_overlay()
        except Exception as ex:
            logger.exception("start_playback error: %s", ex)
            self._show_final_error()

    async def _cycle_speed(self):
        self._speed_idx = (self._speed_idx + 1) % len(self._speeds)
        rate = self._speeds[self._speed_idx]
        self.video.playback_rate = rate
        self.speed_text.value = f"{rate}x"
        try:
            self.video.update()
            self.speed_text.update()
        except Exception:
            pass

    def _hide_overlay(self):
        if not self._overlay_hidden:
            self._overlay_hidden = True
            self.overlay.visible = False
            with contextlib.suppress(Exception):
                self.update()

    # --- Error handling & retry ---

    def _on_error(self, e):
        err_msg = str(e.data) if hasattr(e, "data") and e.data else str(e)
        logger.debug("on_error: %s", err_msg)
        if "Cannot seek" in err_msg or "force-seekable" in err_msg:
            return
        if self._is_final_error:
            return

        self._retry_count += 1
        if self._retry_count <= STREAM_RETRY_MAX and self.resource.startswith("http"):
            self.status_text.value = (
                f"Stream error, retrying ({self._retry_count}/{STREAM_RETRY_MAX})..."
            )
            self.loading_ring.visible = True
            self.overlay.visible = True
            self.update()
            self.page.run_task(self._retry_playback)
        else:
            self._show_final_error()

    def _show_final_error(self):
        self._is_final_error = True
        self.status_text.value = "Failed to load. Tap to go back."
        self.loading_ring.visible = False
        self.overlay.visible = True
        self.overlay.on_click = lambda _: self.page.run_task(self.handle_close)
        self.update()

    async def _retry_playback(self):
        try:
            await asyncio.sleep(STREAM_RETRY_DELAY)
            if self.video and not self._is_final_error:
                self.video.playlist = [
                    fv.VideoMedia(self.resource, http_headers=self.http_headers),
                ]
                await self.video.play()
                self.overlay.visible = False
                self._retry_count = 0
                self.update()
        except Exception:
            self._show_final_error()

    def _on_complete(self, e):
        if re.match(r"https?://", self.resource):
            if self._reconnect_count < STREAM_RECONNECT_MAX:
                self._reconnect_count += 1
                self.page.run_task(self._reconnect_stream)
            else:
                self.status_text.value = "Stream ended. Tap to go back."
                self.loading_ring.visible = False
                self.overlay.visible = True
                self.overlay.on_click = lambda _: self.page.run_task(self.handle_close)
                self.update()

    async def _reconnect_stream(self):
        try:
            if self.video:
                self.video.playlist = [
                    fv.VideoMedia(self.resource, http_headers=self.http_headers),
                ]
                self.overlay.visible = False
                self.update()
        except Exception:
            pass

    # --- Close ---

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

    async def _on_back(self, e=None):
        await self.handle_close()
        if self.on_close:
            try:
                result = self.on_close()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                pass
