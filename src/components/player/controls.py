"""Control builders for ImmersivePlayer."""

import flet as ft
import flet_video as fv

from core.theme import AppColors


def build_player_controls(player_inst) -> fv.AdaptiveVideoControls:
    """Build adaptive player controls for touch and TV/Desktop modes."""
    speed_container = ft.Container(
        content=player_inst.speed_text,
        padding=ft.Padding(8, 4, 8, 4),
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
    title_text = ft.Text(
        player_inst.title or "Now Playing",
        color=ft.Colors.WHITE,
        weight=ft.FontWeight.W_500,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    sub_btn = ft.IconButton(
        icon=ft.Icons.SUBTITLES_ROUNDED,
        icon_color=ft.Colors.WHITE,
        tooltip="Subtitles",
        on_click=lambda e: player_inst.page.run_task(player_inst._pick_subtitles),
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
                sub_btn,
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
                sub_btn,
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
