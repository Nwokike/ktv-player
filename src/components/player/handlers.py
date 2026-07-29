"""Event handlers for ImmersivePlayer."""

import logging
import re

import flet as ft

from core.constants import STREAM_RECONNECT_MAX

logger = logging.getLogger(__name__)


async def cycle_speed(player_inst):
    """Cycle playback speed between 0.5x, 1.0x, 1.25x, 1.5x, 2.0x."""
    player_inst._speed_idx = (player_inst._speed_idx + 1) % len(player_inst._speeds)
    rate = player_inst._speeds[player_inst._speed_idx]
    player_inst.video.playback_rate = rate
    player_inst.speed_text.value = f"{rate}x"
    try:
        player_inst.video.update()
        player_inst.speed_text.update()
    except Exception as ex:
        logger.warning("Failed to update speed UI: %s", ex)


async def pick_subtitles(player_inst):
    """Open FilePicker for .srt and .vtt subtitle files."""
    if not hasattr(player_inst.page, "_sub_file_picker"):
        picker = ft.FilePicker()
        player_inst.page._sub_file_picker = picker
        player_inst.page.overlay.append(picker)
        player_inst.page.update()

    try:
        files = await player_inst.page._sub_file_picker.pick_files(
            dialog_title="Select Subtitle File",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["srt", "vtt"],
            allow_multiple=False,
        )
        if files and files[0].path:
            sub_path = files[0].path
            from flet_video import VideoSubtitleTrack

            custom_track = VideoSubtitleTrack(
                src=sub_path,
                title=files[0].name,
            )
            player_inst.video.subtitle_track = custom_track
            player_inst.video.update()
    except Exception as ex:
        logger.warning("Subtitle pick failed: %s", ex)


def handle_stream_complete(player_inst, e: ft.ControlEvent):
    """Handle stream completion / reconnection logic."""
    if re.match(r"https?://", player_inst.resource):
        if player_inst._reconnect_count < STREAM_RECONNECT_MAX:
            player_inst._reconnect_count += 1
            player_inst._overlay_hidden = False
            player_inst.status_text.value = f"Reconnecting stream ({player_inst._reconnect_count}/{STREAM_RECONNECT_MAX})..."
            player_inst.loading_ring.visible = True
            player_inst.overlay.visible = True
            player_inst._enable_tap_to_close()
            player_inst.update()
            player_inst.page.run_task(reconnect_stream, player_inst)
        else:
            player_inst._show_final_error()


async def reconnect_stream(player_inst):
    """Attempt live stream reconnection."""
    if player_inst._is_closing:
        return

    try:
        if player_inst.video:
            from flet_video import VideoMedia

            player_inst.video.playlist = [
                VideoMedia(player_inst.resource, http_headers=player_inst.http_headers),
            ]
            player_inst.video.update()
            await player_inst.video.play()
    except Exception as ex:
        logger.debug("Failed to reconnect stream: %s", ex)
        player_inst._show_final_error()
