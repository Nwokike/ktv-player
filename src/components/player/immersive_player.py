import flet as ft
import flet_video as fv

class ImmersivePlayer(ft.Stack):
    def __init__(self, resource: str, on_close: callable = None):
        super().__init__()
        self.resource = resource
        self.on_close = on_close
        self.expand = True

        # Native media_kit controls handling hardware acceleration and fullscreen
        self.video = fv.Video(
            playlist=[fv.VideoMedia(self.resource)],
            autoplay=True,
            expand=True,
            show_controls=True, 
            volume=100,
            wakelock=True, 
            filter_quality=ft.FilterQuality.MEDIUM, 
            pause_upon_entering_background_mode=True,
            resume_upon_entering_foreground_mode=True,
        )

        self.back_btn = ft.Container(
            content=ft.IconButton(
                icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                icon_color=ft.Colors.WHITE,
                icon_size=22,
                bgcolor=ft.Colors.BLACK_45, 
                on_click=self.handle_close,
            ),
            left=15,
            top=40, # Safely clears the Android status bar/notch in portrait
        )

        self.controls = [
            ft.Container(expand=True, bgcolor=ft.Colors.BLACK), 
            self.video,
            self.back_btn
        ]

    def handle_close(self, e):
        # We REMOVED the self.page.run_task(self.video.stop) here!
        # Flet automatically disposes of the video instance when we route away, 
        # so removing it manually causes a race condition and crashes the app.
        
        if self.on_close:
            # Smart callback handler
            try:
                self.on_close(e)
            except TypeError:
                self.on_close()