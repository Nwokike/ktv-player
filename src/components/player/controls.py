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
    title_container = ft.Container(
        content=title_text,
        expand=True,
        padding=ft.Padding(4, 0, 8, 0),
    )

    # In-player Favorite Star Button
    is_fav = player_inst.resource in (state.favorites or [])
    fav_color = AppColors.PRIMARY if is_fav else ft.Colors.WHITE
    fav_icon = ft.Icons.STAR_ROUNDED if is_fav else ft.Icons.STAR_BORDER_ROUNDED

    fav_btn = ft.IconButton(
        icon=fav_icon,
        icon_color=fav_color,
        tooltip="Remove from Favorites" if is_fav else "Add to Favorites",
    )

    def _on_toggle_fav(e):
        toggle_favorite(player_inst.resource, state)
        new_fav = player_inst.resource in (state.favorites or [])

        fav_btn.icon = (
            ft.Icons.STAR_ROUNDED if new_fav else ft.Icons.STAR_BORDER_ROUNDED
        )
        fav_btn.icon_color = AppColors.PRIMARY if new_fav else ft.Colors.WHITE
        fav_btn.tooltip = "Remove from Favorites" if new_fav else "Add to Favorites"
        try:
            fav_btn.update()
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
        tooltip="Subtitles",
        on_click=lambda e: player_inst.page.run_task(player_inst._pick_subtitles),
    )

    camera_btn = ft.IconButton(
        icon=ft.Icons.CAMERA_ALT_ROUNDED,
        icon_color=ft.Colors.WHITE,
        tooltip="Take Snapshot",
        on_click=lambda e: player_inst.page.run_task(player_inst._take_screenshot),
    )

    settings_btn = ft.IconButton(
        icon=ft.Icons.SETTINGS_ROUNDED,
        icon_color=ft.Colors.WHITE,
        tooltip="Player & Snapshot Settings",
        on_click=lambda e: player_inst.page.run_task(player_inst._open_player_settings),
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
            primary_button_bar=[
                fv.VideoSpacer(flex=2),
                fv.VideoPlayOrPauseButton(icon_size=48.0),
                fv.VideoSpacer(flex=2),
            ],
            top_button_bar_margin=ft.Margin(16, 35, 16, 0),
            top_button_bar=[
                back_btn,
                title_container,
                fav_btn,
                camera_btn,
                sub_btn,
                settings_btn,
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
            toggle_fullscreen_on_double_press=False,
            play_and_pause_on_tap=False,
            hide_mouse_on_controls_removal=False,
            primary_button_bar=[
                fv.VideoSpacer(flex=2),
                fv.VideoPlayOrPauseButton(icon_size=32.0),
                fv.VideoSpacer(flex=2),
            ],
            top_button_bar=[
                back_btn,
                title_container,
                fav_btn,
                camera_btn,
                sub_btn,
                settings_btn,
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
            seek_bar_buffer_color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE),
            seek_bar_hover_height=8,
            volume_bar_active_color=AppColors.PRIMARY,
            controls_hover_duration=ft.Duration(seconds=4),
        ),
    )
