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
        player_inst.video.controls = player_inst._build_controls()
        player_inst.video.update()
        if hasattr(player_inst.speed_text, "update"):
            player_inst.speed_text.update()
    except Exception as ex:
        logger.warning("Failed to update speed UI: %s", ex)


async def pick_subtitles(player_inst):
    """Open Subtitle Track selection dialog or FilePicker for .srt and .vtt subtitle files."""
    from flet.controls.services.file_picker import FilePicker, FilePickerFileType
    from flet_video import VideoSubtitleTrack

    async def _select_auto(e=None):
        try:
            player_inst.video.subtitle_track = VideoSubtitleTrack.auto()
            player_inst.video.update()
        except Exception as ex:
            logger.warning("Auto subtitle selection failed: %s", ex)
        _close_dialog()

    async def _select_off(e=None):
        try:
            player_inst.video.subtitle_track = VideoSubtitleTrack.none()
            player_inst.video.update()
        except Exception as ex:
            logger.warning("Disable subtitles failed: %s", ex)
        _close_dialog()

    async def _pick_local(e=None):
        _close_dialog()
        fp = FilePicker()
        try:
            files = await fp.pick_files(
                dialog_title="Select Subtitle File",
                file_type=FilePickerFileType.CUSTOM,
                allowed_extensions=["srt", "vtt"],
                allow_multiple=False,
            )
            if files and files[0].path:
                sub_path = files[0].path
                custom_track = VideoSubtitleTrack(
                    src=sub_path,
                    title=files[0].name,
                )
                player_inst.video.subtitle_track = custom_track
                player_inst.video.update()
        except Exception as ex:
            logger.warning("Local subtitle pick failed: %s", ex)

    def _close_dialog(e=None):
        try:
            dialog.open = False
            player_inst.page.update()
        except Exception:
            pass

    dialog = ft.AlertDialog(
        title=ft.Text("Subtitle Options", size=16, weight=ft.FontWeight.BOLD),
        content=ft.Column(
            controls=[
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.SUBTITLES_ROUNDED),
                    title=ft.Text("Auto (Embedded Track)"),
                    subtitle=ft.Text("Detect automatically from stream"),
                    on_click=_select_auto,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.SUBTITLES_OFF_ROUNDED),
                    title=ft.Text("Off"),
                    subtitle=ft.Text("Disable subtitles"),
                    on_click=_select_off,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED),
                    title=ft.Text("Load Local Subtitle File..."),
                    subtitle=ft.Text("Select .srt or .vtt file"),
                    on_click=_pick_local,
                ),
            ],
            tight=True,
            spacing=4,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=_close_dialog),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    try:
        player_inst.page.show_dialog(dialog)
    except Exception as ex:
        logger.warning("Failed to show subtitle options dialog: %s", ex)


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
