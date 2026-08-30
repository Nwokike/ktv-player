"""Control builders for ImmersivePlayer."""

import flet as ft
import flet_video as fv

from core.state import state
from core.theme import AppColors
from utils.favorites import toggle_favorite


def build_player_controls(player_inst) -> fv.AdaptiveVideoControls:
    """Build adaptive player controls for touch and TV/Desktop modes."""
    speed_container = ft.Container(
        content=player_inst.speed_text,
        padding=ft.Padding(6, 3, 6, 3),
        border_radius=4,
        ink=True,
        on_click=lambda e: player_inst.page.run_task(player_inst._cycle_speed),
    )
    speed_container.tab_index = 0

    back_btn = ft.IconButton(
        icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
        icon_color=ft.Colors.WHITE,
        tooltip="Back",
        on_click=lambda e: player_inst.page.run_task(player_inst._on_back, e),
    )
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
    player_inst.toast_chip = toast_chip
    player_inst.toast_text = toast_text

    # Toast overlays the title slot so it needs no extra bar width
    title_slot = ft.Stack(
        controls=[title_text, toast_chip],
        alignment=ft.Alignment.CENTER,
    )

    # Quality button (in bottom controls alongside speed/settings): appears
    # once stream options are probed (multi-variant and/or multi-audio).
    # Kept mounted with content=None until options are detected to ensure
    # media_kit Flutter widget tree mounts it properly.
    quality_text = ft.Text(
        "Auto",
        size=11,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_600,
        no_wrap=True,
    )
    quality_row = ft.Row(
        controls=[
            ft.Icon(ft.Icons.HIGH_QUALITY, size=14, color=ft.Colors.WHITE),
            quality_text,
        ],
        spacing=2,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    quality_btn = ft.Container(
        content=None,
        padding=0,
        border_radius=4,
        ink=True,
        tooltip="Quality",
        on_click=lambda e: player_inst.page.run_task(player_inst._open_player_settings),
    )
    player_inst.quality_btn = quality_btn
    player_inst.quality_row = quality_row
    player_inst.quality_text = quality_text

    # Audio track button (in bottom controls alongside quality): appears
    # when stream has multiple selectable audio renditions.
    audio_text = ft.Text(
        "Audio",
        size=11,
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_600,
        no_wrap=True,
    )
    audio_row = ft.Row(
        controls=[
            ft.Icon(ft.Icons.AUDIOTRACK_ROUNDED, size=14, color=ft.Colors.WHITE),
            audio_text,
        ],
        spacing=2,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    audio_btn = ft.Container(
        content=None,
        padding=0,
        border_radius=4,
        ink=True,
        tooltip="Audio Track",
        on_click=lambda e: player_inst.page.run_task(player_inst._open_player_settings),
    )
    player_inst.audio_btn = audio_btn
    player_inst.audio_row = audio_row
    player_inst.audio_text = audio_text

    # In-player Favorite Star Button — hidden for deep-link plays
    show_fav = getattr(player_inst, "show_favorite_button", True)
    is_fav = player_inst.resource in (state.favorites or [])
    fav_color = AppColors.PRIMARY if is_fav else ft.Colors.WHITE
    fav_icon = ft.Icons.STAR_ROUNDED if is_fav else ft.Icons.STAR_BORDER_ROUNDED

    btn_style = ft.ButtonStyle(
        padding=ft.Padding(0, 0, 0, 0),
        visual_density=ft.VisualDensity.COMPACT,
    )

    fav_btn = ft.IconButton(
        icon=fav_icon,
        icon_color=fav_color,
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
            notify("⭐ Added to Favorites")
        else:
            notify("Removed from Favorites")

        # Call the async db save in background
        toggle_favorite(player_inst.resource, state)

        try:
            fav_btn.update()
        except Exception:
            pass
        try:
            if hasattr(player_inst, "video") and player_inst.video:
                player_inst.video.update()
        except Exception:
            pass
        try:
            if hasattr(player_inst, "page") and player_inst.page:
                player_inst.page.update()
        except Exception:
            pass

    fav_btn.on_click = _on_toggle_fav

    sub_btn = ft.IconButton(
        icon=ft.Icons.SUBTITLES_ROUNDED,
        icon_color=ft.Colors.WHITE,
        icon_size=18,
        padding=0,
        visual_density=ft.VisualDensity.COMPACT,
        style=btn_style,
        tooltip="Subtitles",
        on_click=lambda e: player_inst.page.run_task(player_inst._pick_subtitles),
    )

    camera_btn = ft.IconButton(
        icon=ft.Icons.CAMERA_ALT_ROUNDED,
        icon_color=ft.Colors.WHITE,
        icon_size=18,
        padding=0,
        visual_density=ft.VisualDensity.COMPACT,
        style=btn_style,
        tooltip="Take Snapshot",
        on_click=lambda e: player_inst.page.run_task(player_inst._take_screenshot),
    )

    settings_btn = ft.IconButton(
        icon=ft.Icons.SETTINGS_ROUNDED,
        icon_color=ft.Colors.WHITE,
        icon_size=18,
        padding=0,
        visual_density=ft.VisualDensity.COMPACT,
        style=btn_style,
        tooltip="Player & Snapshot Settings",
        on_click=lambda e: player_inst.page.run_task(player_inst._open_player_settings),
    )

    # Android Picture-in-Picture (mobile controls only)
    pip_btn = None
    if getattr(player_inst, "pip_available", False):
        pip_btn = ft.IconButton(
            icon=ft.Icons.PICTURE_IN_PICTURE,
            icon_color=ft.Colors.WHITE,
            icon_size=18,
            padding=0,
            visual_density=ft.VisualDensity.COMPACT,
            style=btn_style,
            tooltip="Picture-in-Picture",
            on_click=lambda e: player_inst.page.run_task(player_inst.enter_pip),
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
            # 6s > the 3s toast lifetime: with the default 3s hover hide,
            # mobile controls faded out and took the in-player toast with
            # them before the user could read it (desktop worked because
            # mouse movement resets its timer).
            controls_hover_duration=ft.Duration(seconds=6),
            controls_transition_duration=ft.Duration(milliseconds=300),
            seek_bar_position_color=AppColors.PRIMARY,
            button_bar_button_color=ft.Colors.WHITE,
            button_bar_button_size=18.0,
            primary_button_bar=[
                fv.VideoSpacer(flex=2),
                fv.VideoPlayOrPauseButton(icon_size=48.0),
                fv.VideoSpacer(flex=2),
            ],
            top_button_bar_margin=ft.Margin(16, 35, 16, 0),
            top_button_bar=[
                back_btn,
                title_slot,
            ],
            bottom_button_bar=[
                fv.VideoPositionIndicator(
                    text_style=ft.TextStyle(size=12, color=ft.Colors.WHITE),
                ),
                fv.VideoSpacer(),
                speed_container,
                quality_btn,
                audio_btn,
                *([fav_btn] if show_fav else []),
                camera_btn,
                sub_btn,
                settings_btn,
                *([pip_btn] if pip_btn else []),
                fv.VideoFullscreenButton(icon_color=ft.Colors.WHITE, icon_size=18.0),
            ],
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
            top_button_bar=[
                back_btn,
                title_slot,
            ],
            bottom_button_bar=[
                fv.VideoVolumeButton(slider_width=80, icon_color=ft.Colors.WHITE),
                fv.VideoSpacer(),
                fv.VideoPositionIndicator(
                    text_style=ft.TextStyle(size=12, color=ft.Colors.WHITE),
                ),
                fv.VideoSpacer(),
                speed_container,
                quality_btn,
                audio_btn,
                *([fav_btn] if show_fav else []),
                camera_btn,
                sub_btn,
                settings_btn,
                fv.VideoFullscreenButton(icon_color=ft.Colors.WHITE, icon_size=18.0),
            ],
            seek_bar_position_color=AppColors.PRIMARY,
            seek_bar_buffer_color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE),
            seek_bar_hover_height=8,
            volume_bar_active_color=AppColors.PRIMARY,
            controls_hover_duration=ft.Duration(seconds=4),
        ),
    )
