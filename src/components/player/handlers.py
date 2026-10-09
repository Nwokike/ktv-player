"""Event handlers for ImmersivePlayer."""

import contextlib
import logging
import re

import flet as ft
from flet_video import VideoSubtitleConfiguration

from core.constants import STREAM_RECONNECT_MAX

logger = logging.getLogger(__name__)


async def cycle_speed(player_inst):
    """Cycle playback speed between 0.5x, 1.0x, 1.25x, 1.5x, 2.0x.

    Refuses on a live stream: playback rate on content with no seekable
    timeline does nothing useful and desyncs a live edge.
    """
    if not getattr(player_inst, "speed_available", True):
        from utils.notifications import notify

        notify("Playback speed isn't available on live channels")
        return
    player_inst._speed_idx = (player_inst._speed_idx + 1) % len(player_inst._speeds)
    rate = player_inst._speeds[player_inst._speed_idx]
    player_inst.video.playback_rate = rate
    # Update EVERY branch's speed text (mobile + desktop each built one).
    for text in player_inst._branch_controls("speed_texts", "speed_text"):
        text.value = f"{rate:g}x"
    # Single update: speed_text lives inside video.controls, so video.update()
    # already pushes it — a second child .update() throws or no-ops.
    try:
        player_inst.video.update()
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
            # The service must mount before first use: without an update the
            # native binding may not exist on Android and pick_files returns
            # None / raises.
            with contextlib.suppress(Exception):
                player_inst.page.update()
        try:
            files = await picker.pick_files(
                dialog_title="Select Subtitle File",
                file_type=FilePickerFileType.CUSTOM,
                allowed_extensions=["srt", "vtt"],
                allow_multiple=False,
                # Web has no filesystem path: without_data, FilePickerFile
                # .bytes is always None and the bytes-subtitle branch below
                # is dead code.
                with_data=True,
            )
            if not files:
                return
            picked = files[0]
            if picked.path:
                sub_src = picked.path
            elif getattr(picked, "bytes", None):
                # Web: no filesystem path exists, only bytes. flet_video
                # accepts raw subtitle text as src — decode and pass through.
                try:
                    sub_src = bytes(picked.bytes).decode("utf-8-sig")
                except Exception:
                    logger.warning("Local subtitle bytes are not decodable text")
                    return
            else:
                from utils.notifications import notify_warning

                notify_warning("Subtitles are not available on this platform.")
                return
            player_inst.selected_subtitle = "local"
            player_inst.video.subtitle_track = VideoSubtitleTrack(
                src=sub_src,
                title=picked.name,
            )
            player_inst.video.update()
            from utils.notifications import notify

            notify("Subtitle loaded.")
        except Exception as ex:
            logger.warning("Local subtitle pick failed: %s", ex)

    def _close_dialog(e=None):
        try:
            player_inst.page.pop_dialog()
        except Exception:
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

    # NOTE: tracks are fetched UNCONDITIONALLY (not gated on variants): a
    # single-variant stream can still carry 2+ audio renditions, and the old
    # `... or [] if variants else []` ternary hid them.
    variants = await player_inst.list_variants() or []
    tracks = await player_inst.list_audio_tracks() or []
    if not variants and not tracks:
        return

    def _close_dialog(e=None):
        try:
            player_inst.page.pop_dialog()
        except Exception:
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
            # Fixed max: scroll is already AUTO, and counting Divider/header
            # rows as 52px mistallies the height.
            height=420,
        ),
        actions=[ft.TextButton("Cancel", on_click=_close_dialog)],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    try:
        player_inst.page.show_dialog(dialog)
    except Exception as ex:
        logger.warning("Failed to show quality picker: %s", ex)


_SUBTITLE_SIZE_LABELS = {"small": "Small", "medium": "Medium", "large": "Large"}


async def open_player_settings(player_inst):
    """Open Player & Snapshot Settings dialog using page.show_dialog."""
    from core.theme import AppColors
    from database.manager import db_manager

    if not hasattr(player_inst, "include_subtitles_in_snapshot"):
        player_inst.include_subtitles_in_snapshot = True
    if not hasattr(player_inst, "snapshot_format"):
        player_inst.snapshot_format = "image/png"
    try:
        stored_size = await db_manager.get_setting("subtitle_size", "medium")
    except Exception:
        stored_size = "medium"
    if stored_size not in _SUBTITLE_SIZE_LABELS:
        stored_size = "medium"

    def _toggle_subtitles_snapshot(e):
        player_inst.include_subtitles_in_snapshot = e.control.value
        player_inst.page.run_task(
            db_manager.set_setting,
            "snapshot_subtitles",
            "1" if e.control.value else "0",
        )

    def _change_format(e):
        player_inst.snapshot_format = e.control.value
        player_inst.page.run_task(
            db_manager.set_setting, "snapshot_format", e.control.value
        )

    def _change_subtitle_size(e):
        key = e.control.value
        if key not in _SUBTITLE_SIZE_LABELS:
            return
        player_inst.page.run_task(db_manager.set_setting, "subtitle_size", key)
        try:
            from components.player.immersive_player import (
                ImmersivePlayer as _PlayerCls,
            )

            size = _PlayerCls._SUBTITLE_SIZES[key]
            player_inst.video.subtitle_configuration = VideoSubtitleConfiguration(
                text_style=ft.TextStyle(
                    size=size,
                    color=ft.Colors.WHITE,
                    weight=ft.FontWeight.W_600,
                    bgcolor=ft.Colors.BLACK_54,
                ),
                text_align=ft.TextAlign.CENTER,
                visible=True,
            )
            player_inst.video.update()
        except Exception as ex:
            logger.warning("Subtitle size apply failed: %s", ex)

    def _change_fit(e):
        fit_val = e.control.value.upper()
        if hasattr(ft.BoxFit, fit_val):
            player_inst.video.fit = getattr(ft.BoxFit, fit_val)
            with contextlib.suppress(Exception):
                player_inst.video.update()

    # --- Stream (Quality & Audio) ---
    # Restored to Settings: it is the reliable, always-reachable surface for
    # quality/audio switching. The in-controls chip is gated behind a probe
    # and was not reliably visible, so quality/audio now live here (and the
    # chip, when visible, opens the same options). Populated from the already
    # probed caches and refreshed in the background so the dialog opens
    # instantly instead of blocking on a manifest fetch.
    if not hasattr(player_inst, "_current_variant"):
        player_inst._current_variant = None
    if not hasattr(player_inst, "_current_audio"):
        player_inst._current_audio = None

    has_variants = (
        getattr(player_inst, "_variants_cache", None) is not None
        and len(player_inst._variants_cache) > 1
    )
    has_audio = (
        getattr(player_inst, "_audio_tracks_cache", None) is not None
        and len(player_inst._audio_tracks_cache) >= 2
    )

    stream_header = ft.Text(
        "Stream (Quality & Audio)",
        size=13,
        weight=ft.FontWeight.W_600,
        color=AppColors.PRIMARY,
        visible=has_variants or has_audio,
    )
    stream_divider = ft.Divider(visible=has_variants or has_audio)

    # NOTE: Dropdown uses on_select (NOT on_change) in flet 1.0.1 — verified
    # against flet/controls/material/dropdown.py (on_select exists; the class
    # has no on_change attribute). Do not "fix" this to on_change.
    def _safe_variant(value: str):
        if value == "auto":
            return None
        try:
            idx = int(value)
        except (TypeError, ValueError):
            return None
        valid = {str(v.get("index")) for v in (player_inst._variants_cache or [])}
        return idx if str(idx) in valid else None

    def _safe_audio(value: str):
        if value == "default":
            return None
        valid = {t.get("name") for t in (player_inst._audio_tracks_cache or [])}
        return value if value in valid else None

    quality_dd = ft.Dropdown(
        label="Quality",
        value=(
            "auto"
            if player_inst._current_variant is None
            else str(player_inst._current_variant)
        ),
        options=(
            [ft.dropdown.Option("auto", "Auto (Adaptive)")]
            + [
                ft.dropdown.Option(str(v["index"]), v["label"])
                for v in (getattr(player_inst, "_variants_cache", []) or [])
            ]
            if has_variants
            else [ft.dropdown.Option("auto", "Auto (Adaptive)")]
        ),
        width=240,
        visible=has_variants,
        on_select=lambda e: player_inst.page.run_task(
            player_inst.apply_variant,
            _safe_variant(e.control.value),
        ),
    )
    audio_dd = ft.Dropdown(
        label="Audio Track",
        value=(
            "default"
            if player_inst._current_audio is None
            else player_inst._current_audio
        ),
        options=(
            [ft.dropdown.Option("default", "Default")]
            + [
                ft.dropdown.Option(
                    t["name"],
                    t["name"] + (f" ({t['language']})" if t["language"] else ""),
                )
                for t in (getattr(player_inst, "_audio_tracks_cache", []) or [])
            ]
            if has_audio
            else [ft.dropdown.Option("default", "Default")]
        ),
        width=240,
        visible=has_audio,
        on_select=lambda e: player_inst.page.run_task(
            player_inst.apply_audio,
            _safe_audio(e.control.value),
        ),
    )

    async def _refresh_stream_options():
        try:
            # Unconditional (see open_quality_picker note): single-variant
            # streams can still carry multiple audio renditions.
            variants = await player_inst.list_variants() or []
            tracks = await player_inst.list_audio_tracks() or []
        except Exception:
            return
        has_q = len(variants) > 1
        has_a = len(tracks) >= 2
        quality_dd.visible = has_q
        if has_q:
            quality_dd.options = [ft.dropdown.Option("auto", "Auto (Adaptive)")] + [
                ft.dropdown.Option(str(v["index"]), v["label"]) for v in variants
            ]
            valid_idx = {str(v.get("index")) for v in variants}
            cur = (
                "auto"
                if player_inst._current_variant is None
                else str(player_inst._current_variant)
            )
            # Stale pin (variant list changed under us) falls back to Auto
            # instead of an invalid Dropdown value.
            quality_dd.value = cur if cur == "auto" or cur in valid_idx else "auto"
            if quality_dd.value == "auto" and player_inst._current_variant is not None:
                player_inst._current_variant = None
        audio_dd.visible = has_a
        if has_a:
            audio_dd.options = [ft.dropdown.Option("default", "Default")] + [
                ft.dropdown.Option(
                    t["name"],
                    t["name"] + (f" ({t['language']})" if t["language"] else ""),
                )
                for t in tracks
            ]
            valid_names = {t.get("name") for t in tracks}
            cur_a = (
                "default"
                if player_inst._current_audio is None
                else player_inst._current_audio
            )
            audio_dd.value = (
                cur_a if cur_a == "default" or cur_a in valid_names else "default"
            )
            if audio_dd.value == "default" and player_inst._current_audio is not None:
                player_inst._current_audio = None
        stream_header.visible = has_q or has_a
        stream_divider.visible = has_q or has_a
        # Single update: four sibling .update() calls = four round-trips with
        # partial flicker. The dialog owns them all.
        with contextlib.suppress(Exception):
            dialog.update()

    # Double-open guard lives on the player instance: a function-local flag
    # would reset on every call and guard nothing. `is True` (not truthiness):
    # on MagicMock test doubles getattr auto-creates a truthy child mock, and
    # only an identity check distinguishes it from a real True.
    if getattr(player_inst, "_settings_open", False) is True:
        return

    def _close_dialog(e=None):
        player_inst._settings_open = False
        try:
            player_inst.page.pop_dialog()
        except Exception:
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
                stream_header,
                quality_dd,
                audio_dd,
                stream_divider,
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
                ft.Divider(),
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
                ft.Dropdown(
                    label="Subtitle Size",
                    value=stored_size,
                    options=[
                        ft.dropdown.Option(k, v)
                        for k, v in _SUBTITLE_SIZE_LABELS.items()
                    ],
                    on_select=_change_subtitle_size,
                    width=240,
                ),
            ],
            tight=True,
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            ft.TextButton("Done", on_click=_close_dialog),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )

    player_inst._settings_open = True
    try:
        player_inst.page.show_dialog(dialog)
        player_inst.page.run_task(_refresh_stream_options)
    except Exception as ex:
        player_inst._settings_open = False
        logger.warning("Failed to show player settings dialog: %s", ex)


def handle_stream_complete(player_inst, e: ft.ControlEvent):
    """Handle stream completion / reconnection logic."""
    # A dead-error overlay owns the screen: never paint "Reconnecting" over it.
    # `is True` (not truthiness): MagicMock test doubles auto-create truthy
    # children for any attribute, and only identity distinguishes them.
    if getattr(player_inst, "_is_final_error", False) is True:
        return
    # Finite VOD streams that reach the end should not reconnect
    dur = getattr(player_inst, "_last_duration", 0.0)
    pos = getattr(player_inst, "_last_position", 0.0)
    if (
        isinstance(dur, (int, float))
        and isinstance(pos, (int, float))
        and dur > 0
        and pos >= max(0.0, dur - 5.0)
    ):
        return

    if re.match(r"https?://", player_inst.resource or ""):
        if player_inst._reconnect_count < STREAM_RECONNECT_MAX:
            player_inst._reconnect_count += 1
            player_inst._show_progress(
                f"Reconnecting stream ({player_inst._reconnect_count}/{STREAM_RECONNECT_MAX})..."
            )
            try:
                page = getattr(player_inst, "safe_page", None) or getattr(
                    player_inst, "page", None
                )
                if page:
                    page.run_task(reconnect_stream, player_inst)
            except Exception:
                pass
        else:
            player_inst._show_final_error()
    else:
        # Non-HTTP resources (local files, content URIs) can't reconnect:
        # say so instead of a silent black screen.
        player_inst._show_final_error("Playback ended.")


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
            # Reapply user state the fresh playlist item doesn't carry:
            # speed, subtitles, and pinned variant/audio labels.
            try:
                rate = getattr(player_inst, "_speeds", [1.0])[
                    getattr(player_inst, "_speed_idx", 0)
                ]
                player_inst.video.playback_rate = rate
            except Exception:
                pass
            player_inst.video.update()
            player_inst._reconnect_count = 0
            player_inst._start_watchdog()
    except Exception as ex:
        logger.debug("Failed to reconnect stream: %s", ex)
        player_inst._show_final_error()
