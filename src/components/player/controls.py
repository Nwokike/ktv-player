"""Control builders for ImmersivePlayer."""

import flet as ft
import flet_video as fv

from core.state import state
from core.theme import AppColors
from utils.favorites import toggle_favorite_async


def _chip_style() -> ft.ButtonStyle:
    return ft.ButtonStyle(
        padding=ft.Padding(0, 0, 0, 0),
        visual_density=ft.VisualDensity.COMPACT,
    )


def _make_speed_chip(player_inst) -> ft.Container:
    # Fresh Text per branch (single-parent rule): the old shared
    # player_inst.speed_text got two parents when mobile + desktop both
    # built, and speed_container was overwritten by the second branch.
    speed_text = ft.Text(
        "1.0x",
        size=11,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_600,
    )
    _stash(player_inst, "speed_texts", speed_text)
    chip = ft.Container(
        content=speed_text,
        padding=ft.Padding(6, 3, 6, 3),
        border_radius=4,
        ink=True,
        on_click=lambda e: player_inst.page.run_task(player_inst._cycle_speed),
        # Hidden until duration metadata arrives: live streams never get a
        # duration, so the chip never appears for a channel.
        visible=getattr(player_inst, "speed_available", True),
    )
    _stash(player_inst, "speed_containers", chip)
    # Legacy singular refs (register-style consumers; new code uses the
    # lists). Always overwritten, never hasattr-guarded — hasattr is always
    # True on MagicMock test doubles.
    player_inst.speed_container = chip
    player_inst.speed_text = speed_text
    return chip


def _make_back_button(player_inst) -> ft.IconButton:
    return ft.IconButton(
        icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
        icon_color=ft.Colors.WHITE,
        tooltip="Back",
        on_click=lambda e: player_inst.page.run_task(player_inst._on_back, e),
    )


def _stash(player_inst, attr: str, value) -> None:
    """Collect per-branch control instances.

    Each AdaptiveVideoControls branch owns FRESH instances (single-parent
    rule), so stashed refs are LISTS — one entry per branch. Refresh/probe
    code loops over all of them instead of touching a single shared object.
    """
    existing = getattr(player_inst, attr, None)
    if isinstance(existing, list):
        existing.append(value)
    else:
        setattr(player_inst, attr, [value])


def _make_title_slot(player_inst) -> ft.Stack:
    # Full title, no width machinery — the bar clips whatever doesn't fit.
    # (Every dynamic-resizing attempt since v2.0 failed across
    # rotation/fullscreen; the player now shows the name as-is.)
    title_text = ft.Text(
        player_inst.title or "Now Playing",
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_500,
    )

    # In-player toast chip. It lives INSIDE the video controls because the
    # fullscreen route (pushed by media_kit on the root navigator, above the
    # whole Flet page tree) re-renders these same controls — the only Flet
    # surface visible in fullscreen. Overlays placed next to the Video in a
    # Stack are covered in fullscreen; this chip is not.
    toast_text = ft.Text(
        "",
        color=ft.Colors.WHITE,
        size=13,
        weight=ft.FontWeight.W_500,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )
    toast_chip = ft.Container(
        content=toast_text,
        bgcolor=ft.Colors.with_opacity(0.85, ft.Colors.BLACK),
        border_radius=8,
        padding=ft.Padding(12, 6, 12, 6),
        visible=False,
    )
    _stash(player_inst, "toast_chips", toast_chip)
    _stash(player_inst, "toast_texts", toast_text)
    # Legacy singular refs (did_mount/register_fullscreen_toast; new code uses
    # the lists). Always overwritten — and NOT hasattr-guarded, because
    # hasattr is always True on MagicMock test doubles.
    player_inst.toast_chip = toast_chip
    player_inst.toast_text = toast_text

    # Toast overlays the title slot so it needs no extra bar width
    return ft.Stack(
        controls=[title_text, toast_chip],
        alignment=ft.Alignment.CENTER,
    )


def _make_option_chip(
    player_inst,
    attr: str,
    row_attr: str,
    text_attr: str,
    icon: object,
    tooltip: str,
    default_label: str,
    open_picker: str,
) -> ft.Container:
    """Quality/audio chip with a stable minimum size.

    Old shape was content=None + padding=0 (zero-size, invisible) until the
    probe filled it — layout shifted when it appeared, and if the probe path
    ever skipped its update the button stayed permanently collapsed. The chip
    now renders its default label immediately with a fixed min width.
    """
    from components.player.handlers import open_quality_picker

    label = ft.Text(
        default_label,
        size=11,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_600,
        no_wrap=True,
    )
    row = ft.Row(
        controls=[
            ft.Icon(icon, size=14, color=ft.Colors.WHITE),
            label,
        ],
        spacing=2,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    chip = ft.Container(
        content=row,
        padding=ft.Padding(6, 3, 6, 3),
        border_radius=4,
        ink=True,
        tooltip=tooltip,
        on_click=lambda e: (
            player_inst.page.run_task(open_quality_picker, player_inst)
            if open_picker == "picker"
            else player_inst.page.run_task(player_inst._open_player_settings)
        ),
    )
    _stash(player_inst, attr + "s", chip)
    _stash(player_inst, row_attr + "s", row)
    _stash(player_inst, text_attr + "s", label)
    # Legacy singular refs (tests + hand-built players). Always overwritten,
    # never hasattr-guarded (hasattr is always True on MagicMock doubles).
    setattr(player_inst, attr, chip)
    setattr(player_inst, row_attr, row)
    setattr(player_inst, text_attr, label)
    return chip


def _make_fav_button(player_inst, btn_style: ft.ButtonStyle) -> ft.IconButton | None:
    # In-player Favorite Star Button — hidden for deep-link plays.
    # Favorite state is recomputed from state.favorites on every build (not a
    # build-time snapshot), so a toggle from Search/Home is reflected here.
    if not getattr(player_inst, "show_favorite_button", True):
        return None
    is_fav = player_inst.resource in (state.favorites or [])

    fav_btn = ft.IconButton(
        icon=ft.Icons.STAR_ROUNDED if is_fav else ft.Icons.STAR_BORDER_ROUNDED,
        icon_color=AppColors.PRIMARY if is_fav else ft.Colors.WHITE,
        icon_size=18,
        padding=0,
        visual_density=ft.VisualDensity.COMPACT,
        style=btn_style,
        tooltip="Remove from Favorites" if is_fav else "Add to Favorites",
        data=is_fav,
    )

    def _on_toggle_fav(e):
        from utils.notifications import notify

        # Toggle state synchronously for UI
        new_fav = not fav_btn.data
        fav_btn.data = new_fav

        fav_btn.icon = (
            ft.Icons.STAR_ROUNDED if new_fav else ft.Icons.STAR_BORDER_ROUNDED
        )
        fav_btn.icon_color = AppColors.PRIMARY if new_fav else ft.Colors.WHITE
        fav_btn.tooltip = "Remove from Favorites" if new_fav else "Add to Favorites"

        if new_fav:
            notify("Added to Favorites")
        else:
            notify("Removed from Favorites")

        # Audio confirmation: unlike the toast chip, sound survives native
        # fullscreen (Android phone and TV only; desktop is a no-op).
        from utils.sfx import play_click

        play_click()

        # Awaited DB save via page task (not bare fire-and-forget): failures
        # surface instead of dying as an un-retrieved coroutine.
        try:
            page = getattr(player_inst, "safe_page", None) or getattr(
                player_inst, "page", None
            )
            if page is not None:
                page.run_task(toggle_favorite_async, player_inst.resource, state)
        except Exception:
            pass

        # Single update: fav_btn lives INSIDE video.controls (serialized as
        # part of the native Video value, not an independently mounted
        # control), so video.update() already pushes it. Child .update() and
        # page.update() are redundant at best, throwing at worst.
        try:
            if getattr(player_inst, "video", None):
                player_inst.video.update()
        except Exception:
            pass

    fav_btn.on_click = _on_toggle_fav
    return fav_btn


def _icon_button(
    player_inst, icon: object, tooltip: str, handler: str, btn_style: ft.ButtonStyle
) -> ft.IconButton:
    return ft.IconButton(
        icon=icon,
        icon_color=ft.Colors.WHITE,
        icon_size=18,
        padding=0,
        visual_density=ft.VisualDensity.COMPACT,
        style=btn_style,
        tooltip=tooltip,
        on_click=lambda e: player_inst.page.run_task(getattr(player_inst, handler)),
    )


def build_top_bar(player_inst, btn_style: ft.ButtonStyle) -> list:
    """Fresh top-bar instances for ONE AdaptiveVideoControls branch."""
    return [
        _make_back_button(player_inst),
        _make_title_slot(player_inst),
    ]


def build_bottom_bar(player_inst, btn_style: ft.ButtonStyle, *, desktop: bool) -> list:
    """Fresh bottom-bar instances for ONE AdaptiveVideoControls branch.

    Each branch gets its own button objects: sharing one instance across the
    material + material_desktop trees risks dirty-tracking conflicts and
    double-mount errors (Flet controls expect a single parent).
    """
    quality_btn = _make_option_chip(
        player_inst,
        "quality_btn",
        "quality_row",
        "quality_text",
        ft.Icons.HIGH_QUALITY,
        "Quality",
        "Auto",
        "picker",
    )
    audio_btn = _make_option_chip(
        player_inst,
        "audio_btn",
        "audio_row",
        "audio_text",
        ft.Icons.AUDIOTRACK_ROUNDED,
        "Audio Track",
        "Audio",
        "picker",
    )
    fav_btn = _make_fav_button(player_inst, btn_style)
    bar: list = []
    if desktop:
        bar.append(fv.VideoVolumeButton(slider_width=80, icon_color=ft.Colors.WHITE))
        bar.append(fv.VideoSpacer())
    bar.append(
        fv.VideoPositionIndicator(
            text_style=ft.TextStyle(size=12, color=ft.Colors.WHITE),
        )
    )
    if not desktop:
        # Mobile buffer signal: flet_video has no on_buffer* event, so the
        # seek-bar buffer color is the only buffering indication.
        pass
    bar.append(fv.VideoSpacer())
    bar.append(_make_speed_chip(player_inst))
    bar.append(quality_btn)
    bar.append(audio_btn)
    if fav_btn is not None:
        bar.append(fav_btn)
    bar.append(
        _icon_button(
            player_inst,
            ft.Icons.CAMERA_ALT_ROUNDED,
            "Take Snapshot",
            "_take_screenshot",
            btn_style,
        )
    )
    bar.append(
        _icon_button(
            player_inst,
            ft.Icons.SUBTITLES_ROUNDED,
            "Subtitles",
            "_pick_subtitles",
            btn_style,
        )
    )
    bar.append(
        _icon_button(
            player_inst,
            ft.Icons.SETTINGS_ROUNDED,
            "Player & Snapshot Settings",
            "_open_player_settings",
            btn_style,
        )
    )
    if not desktop and getattr(player_inst, "pip_available", False):
        bar.append(
            _icon_button(
                player_inst,
                ft.Icons.PICTURE_IN_PICTURE,
                "Picture-in-Picture",
                "enter_pip",
                btn_style,
            )
        )
    bar.append(fv.VideoFullscreenButton(icon_color=ft.Colors.WHITE, icon_size=18.0))
    return bar


def build_player_controls(player_inst) -> fv.AdaptiveVideoControls:
    """Build adaptive player controls for touch and TV/Desktop modes."""
    btn_style = _chip_style()
    mobile_bottom = build_bottom_bar(player_inst, btn_style, desktop=False)
    desktop_bottom = build_bottom_bar(player_inst, btn_style, desktop=True)

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
            seek_bar_buffer_color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE),
            button_bar_button_color=ft.Colors.WHITE,
            button_bar_button_size=18.0,
            primary_button_bar=[
                fv.VideoSpacer(flex=2),
                fv.VideoPlayOrPauseButton(icon_size=48.0),
                fv.VideoSpacer(flex=2),
            ],
            top_button_bar_margin=ft.Margin(16, 35, 16, 0),
            top_button_bar=build_top_bar(player_inst, btn_style),
            bottom_button_bar=mobile_bottom,
        ),
        # --- Desktop / TV (keyboard + D-pad) ---
        material_desktop=fv.MaterialDesktopVideoControls(
            visible_on_mount=True,
            display_seek_bar=True,
            modify_volume_on_scroll=True,
            toggle_fullscreen_on_double_press=False,
            play_and_pause_on_tap=False,
            hide_mouse_on_controls_removal=False,
            button_bar_button_size=18.0,
            primary_button_bar=[
                fv.VideoSpacer(flex=2),
                fv.VideoPlayOrPauseButton(icon_size=32.0),
                fv.VideoSpacer(flex=2),
            ],
            top_button_bar=build_top_bar(player_inst, btn_style),
            bottom_button_bar=desktop_bottom,
            seek_bar_position_color=AppColors.PRIMARY,
            seek_bar_buffer_color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE),
            seek_bar_hover_height=8,
            volume_bar_active_color=AppColors.PRIMARY,
            controls_hover_duration=ft.Duration(seconds=4),
        ),
    )
