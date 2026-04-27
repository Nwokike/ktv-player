import flet as ft
import flet_video as fv
from core.theme import AppColors

def ImmersivePlayer(
    resource: str,
    on_close: callable = None,
):
    # Video control
    video = fv.Video(
        playlist=[fv.VideoMedia(resource)],
        autoplay=True,
        expand=True,
        show_controls=False, # We use custom controls
        volume=100,
        pause_upon_entering_background_mode=True,
    )

    # Brightness Overlay (Simulated)
    brightness_overlay = ft.Container(
        expand=True,
        bgcolor=ft.colors.BLACK,
        opacity=0.0, # 0.0 is brightest, 1.0 is darkest
        visible=True,
    )

    # Gesture Logic
    def handle_vertical_drag(e: ft.DragUpdateEvent):
        # Determine if left side (brightness) or right side (volume)
        # Assuming player fills the width. We use global_x / page width.
        width = e.page.window_width if e.page.window_width else 1920
        is_left_side = e.global_x < (width / 2)
        
        delta = e.delta_y / 200 # Adjust sensitivity
        
        if is_left_side:
            # Adjust Brightness Overlay
            new_opacity = max(0.0, min(0.8, brightness_overlay.opacity + delta))
            brightness_overlay.opacity = new_opacity
            brightness_overlay.update()
        else:
            # Adjust Volume
            new_vol = max(0.0, min(100.0, video.volume - (delta * 100)))
            video.volume = new_vol
            video.update()

    # Main Stack
    return ft.Stack(
        [
            video,
            brightness_overlay,
            ft.GestureDetector(
                on_vertical_drag_update=handle_vertical_drag,
                on_double_tap=lambda _: video.jump_to(0), # Or seek logic
                content=ft.Container(expand=True, bgcolor=ft.colors.TRANSPARENT),
            ),
            # Close button
            ft.Container(
                content=ft.IconButton(
                    icon=ft.icons.CLOSE,
                    icon_color=AppColors.TEXT_PRIMARY,
                    on_click=on_close,
                ),
                alignment=ft.alignment.top_right,
                padding=20,
            )
        ],
        expand=True,
    )
