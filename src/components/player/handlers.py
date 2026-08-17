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
        if hasattr(player_inst.speed_text, "update"):
            player_inst.speed_text.update()
    except Exception as ex:
        logger.warning("Failed to update speed UI: %s", ex)


async def pick_subtitles(player_inst):
    """Open Subtitle Track selection dialog or FilePicker for .srt and .vtt subtitle files."""
    from flet import FilePicker, FilePickerFileType
    from flet_video import VideoSubtitleTrack

    from core.theme import AppColors

    if not hasattr(player_inst, "selected_subtitle"):
        player_inst.selected_subtitle = "auto"

    active_sub = player_inst.selected_subtitle

    async def _select_auto(e=None):
        player_inst.selected_subtitle = "auto"
        try:
            player_inst.video.subtitle_track = VideoSubtitleTrack.auto()
            player_inst.video.update()
        except Exception as ex:
            logger.warning("Auto subtitle selection failed: %s", ex)
        _close_dialog()

    async def _select_off(e=None):
        player_inst.selected_subtitle = "off"
        try:
            player_inst.video.subtitle_track = VideoSubtitleTrack.none()
            player_inst.video.update()
        except Exception as ex:
            logger.warning("Disable subtitles failed: %s", ex)
        _close_dialog()

    async def _pick_local(e=None):
        _close_dialog()
        # Use the singleton FilePicker registered at boot — constructing one
        # inline loses the service registration on Android (see main.py).
        picker = getattr(player_inst.page, "file_picker", None)
        if picker is None:
            picker = FilePicker()
            player_inst.page.services.append(picker)
            player_inst.page.file_picker = picker
        try:
            files = await picker.pick_files(
                dialog_title="Select Subtitle File",
                file_type=FilePickerFileType.CUSTOM,
                allowed_extensions=["srt", "vtt"],
                allow_multiple=False,
            )
            if files and files[0].path:
                player_inst.selected_subtitle = "local"
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

    def _check_icon(is_active: bool):
        return (
            ft.Icon(ft.Icons.CHECK_ROUNDED, color=AppColors.PRIMARY)
            if is_active
            else None
        )

    dialog = ft.AlertDialog(
        title=ft.Text("Subtitles", size=15, weight=ft.FontWeight.W_700),
        content_padding=ft.Padding(0, 8, 0, 0),
        inset_padding=ft.Padding(20, 24, 20, 16),
        content=ft.Column(
            controls=[
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.SUBTITLES_ROUNDED, size=20),
                    title=ft.Text("Auto", size=14, weight=ft.FontWeight.W_500),
                    subtitle=ft.Text(
                        "Detect from stream", size=11, color=AppColors.grey_dim()
                    ),
                    trailing=_check_icon(active_sub == "auto"),
                    on_click=_select_auto,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.SUBTITLES_OFF_ROUNDED, size=20),
                    title=ft.Text("Off", size=14, weight=ft.FontWeight.W_500),
                    subtitle=ft.Text("Disabled", size=11, color=AppColors.grey_dim()),
                    trailing=_check_icon(active_sub == "off"),
                    on_click=_select_off,
                ),
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, size=20),
                    title=ft.Text(
                        "Load Local File…", size=14, weight=ft.FontWeight.W_500
                    ),
                    subtitle=ft.Text(
                        "Select .srt or .vtt", size=11, color=AppColors.grey_dim()
                    ),
                    trailing=_check_icon(active_sub == "local"),
                    on_click=_pick_local,
                ),
            ],
            tight=True,
            spacing=2,
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


async def open_quality_picker(player_inst):
    """Quick Quality / Audio picker opened from the top-bar chip.

    Uses the already-probed variant/track caches, so it opens instantly —
    no manifest fetch on the dialog path.
    """
    from core.theme import AppColors

    variants = await player_inst.list_variants() or []
    tracks = await player_inst.list_audio_tracks() or [] if variants else []
    if not variants and not tracks:
        return

    def _close_dialog(e=None):
        try:
            dialog.open = False
            player_inst.page.update()
        except Exception:
            pass

    def _pick_quality(index):
        _close_dialog()
        player_inst.page.run_task(player_inst.apply_variant, index)

    def _pick_audio(name):
        _close_dialog()
        player_inst.page.run_task(player_inst.apply_audio, name)

    def _check(active: bool):
        return (
            ft.Icon(ft.Icons.CHECK_ROUNDED, color=AppColors.PRIMARY, size=18)
            if active
            else None
        )

    rows: list[ft.Control] = [
        ft.ListTile(
            leading=ft.Icon(ft.Icons.AUTO_AWESOME, size=20),
            title=ft.Text("Auto", size=14),
            subtitle=ft.Text("Adaptive (let the stream decide)", size=11),
            trailing=_check(player_inst._current_variant is None),
            on_click=lambda e: _pick_quality(None),
        )
    ]
    rows.extend(
        ft.ListTile(
            dense=True,
            title=ft.Text(v["label"], size=14),
            trailing=_check(player_inst._current_variant == v["index"]),
            on_click=lambda e, idx=v["index"]: _pick_quality(idx),
        )
        for v in variants
    )

    if len(tracks) >= 2:
        rows.append(ft.Divider())
        rows.append(
            ft.Text(
                "Audio Track",
                size=12,
                weight=ft.FontWeight.W_600,
                color=AppColors.PRIMARY,
            )
        )
        rows.append(
            ft.ListTile(
                dense=True,
                title=ft.Text("Default", size=14),
                trailing=_check(player_inst._current_audio is None),
                on_click=lambda e: _pick_audio(None),
            )
        )
        rows.extend(
            ft.ListTile(
                dense=True,
                title=ft.Text(
                    t["name"] + (f" ({t['language']})" if t["language"] else ""),
                    size=14,
                ),
                trailing=_check(player_inst._current_audio == t["name"]),
                on_click=lambda e, n=t["name"]: _pick_audio(n),
            )
            for t in tracks
        )

    dialog = ft.AlertDialog(
        title=ft.Text("Quality", size=15, weight=ft.FontWeight.W_700),
        content_padding=ft.Padding(0, 8, 0, 0),
        inset_padding=ft.Padding(20, 24, 20, 16),
        content=ft.Container(
            content=ft.Column(
                controls=rows, tight=True, spacing=2, scroll=ft.ScrollMode.AUTO
            ),
            width=280,
            height=min(420, 52 * (len(rows) + 1)),
        ),
        actions=[ft.TextButton("Cancel", on_click=_close_dialog)],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    try:
        player_inst.page.show_dialog(dialog)
    except Exception as ex:
        logger.warning("Failed to show quality picker: %s", ex)


async def open_player_settings(player_inst):
    """Open Player & Snapshot Settings dialog using page.show_dialog."""
    from core.theme import AppColors

    if not hasattr(player_inst, "include_subtitles_in_snapshot"):
        player_inst.include_subtitles_in_snapshot = True
    if not hasattr(player_inst, "snapshot_format"):
        player_inst.snapshot_format = "image/png"

    def _toggle_subtitles_snapshot(e):
        player_inst.include_subtitles_in_snapshot = e.control.value

    def _change_format(e):
        player_inst.snapshot_format = e.control.value

    def _change_fit(e):
        fit_val = e.control.value.upper()
        if hasattr(ft.BoxFit, fit_val):
            player_inst.video.fit = getattr(ft.BoxFit, fit_val)
            try:
                player_inst.video.update()
            except Exception:
                pass

    def _close_dialog(e=None):
        try:
            dialog.open = False
            player_inst.page.update()
        except Exception:
            pass

    dialog = ft.AlertDialog(
        title=ft.Text(
            "Player & Snapshot Settings",
            size=16,
            weight=ft.FontWeight.BOLD,
        ),
        content=ft.Column(
            controls=[
                ft.Text(
                    "Snapshot Preferences",
                    size=13,
                    weight=ft.FontWeight.W_600,
                    color=AppColors.PRIMARY,
                ),
                ft.Switch(
                    label="Include Subtitles in Snapshot",
                    value=player_inst.include_subtitles_in_snapshot,
                    on_change=_toggle_subtitles_snapshot,
                ),
                ft.Dropdown(
                    label="Image Format",
                    value=player_inst.snapshot_format,
                    options=[
                        ft.dropdown.Option("image/png", "PNG (High Quality)"),
                        ft.dropdown.Option("image/jpeg", "JPEG (Compressed)"),
                    ],
                    on_select=_change_format,
                    width=240,
                ),
                ft.Divider(),
                ft.Text(
                    "Screen Aspect Ratio",
                    size=13,
                    weight=ft.FontWeight.W_600,
                    color=AppColors.PRIMARY,
                ),
                ft.Dropdown(
                    label="Video Fit",
                    value=getattr(player_inst.video.fit, "name", "CONTAIN"),
                    options=[
                        ft.dropdown.Option("CONTAIN", "Fit to Screen (Contain)"),
                        ft.dropdown.Option("COVER", "Crop to Fill (Cover)"),
                        ft.dropdown.Option("FILL", "Stretch to Fill (Fill)"),
                    ],
                    on_select=_change_fit,
                    width=240,
                ),
            ],
            tight=True,
            spacing=10,
        ),
        actions=[
            ft.TextButton("Done", on_click=_close_dialog),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    try:
        player_inst.page.show_dialog(dialog)
    except Exception as ex:
        logger.warning("Failed to show player settings dialog: %s", ex)


def handle_stream_complete(player_inst, e: ft.ControlEvent):
    """Handle stream completion / reconnection logic."""
    if re.match(r"https?://", player_inst.resource):
        if player_inst._reconnect_count < STREAM_RECONNECT_MAX:
            player_inst._reconnect_count += 1
            player_inst._show_progress(
                f"Reconnecting stream ({player_inst._reconnect_count}/{STREAM_RECONNECT_MAX})..."
            )
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
            player_inst._start_watchdog()
    except Exception as ex:
        logger.debug("Failed to reconnect stream: %s", ex)
        player_inst._show_final_error()
