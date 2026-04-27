import flet as ft
import flet_video as fv
from core.theme import AppColors

class ImmersivePlayer(ft.Stack):
    def __init__(self, resource: str, on_close: callable = None):
        super().__init__()
        self.resource = resource
        self.on_close = on_close
        self.expand = True

        # Video control
        self.video = fv.Video(
            playlist=[fv.VideoMedia(self.resource)],
            autoplay=True,
            expand=True,
            show_controls=False, # We use custom controls
            volume=100,
            pause_upon_entering_background_mode=True,
        )

        # Brightness Overlay (Simulated)
        self.brightness_overlay = ft.Container(
            expand=True,
            bgcolor=ft.Colors.BLACK,
            opacity=0.0, # 0.0 is brightest, 1.0 is darkest
            visible=True,
        )

        # Close button
        self.close_btn = ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.CLOSE,
                icon_color=AppColors.TEXT_PRIMARY,
                on_click=self.on_close,
            ),
            alignment=ft.Alignment(1, -1),
            padding=20,
        )

        self.controls = [
            self.video,
            self.brightness_overlay,
            ft.GestureDetector(
                on_vertical_drag_update=self.handle_vertical_drag,
                on_double_tap=lambda _: setattr(self.video, "jump_to", 0), # Simplified for now
                content=ft.Container(expand=True, bgcolor=ft.Colors.TRANSPARENT),
            ),
            self.close_btn
        ]

    def handle_vertical_drag(self, e: ft.DragUpdateEvent):
        # Determine if left side (brightness) or right side (volume)
        # Using a default width if page not yet accessible, but usually it is in drag
        width = self.page.window.width if self.page and self.page.window else 1920
        is_left_side = e.global_x < (width / 2)
        
        delta = e.delta_y / 200 # Adjust sensitivity
        
        if is_left_side:
            # Adjust Brightness Overlay
            new_opacity = max(0.0, min(0.8, self.brightness_overlay.opacity + delta))
            self.brightness_overlay.opacity = new_opacity
            self.brightness_overlay.update()
        else:
            # Adjust Volume
            new_vol = max(0.0, min(100.0, self.video.volume - (delta * 100)))
            self.video.volume = new_vol
            self.video.update()
