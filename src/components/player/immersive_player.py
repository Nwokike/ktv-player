import flet as ft
import flet_video as fv

class ImmersivePlayer(ft.Stack):
    def __init__(self, resource: str, on_close: callable = None):
        super().__init__()
        self.resource = resource
        self.on_close = on_close
        self.expand = True

        # We rely strictly on media_kit's native controls for maximum mobile performance.
        # This handles buffering, seeking, volume, and landscape/fullscreen natively.
        self.video = fv.Video(
            playlist=[fv.VideoMedia(self.resource)],
            autoplay=True,
            expand=True,
            show_controls=True, 
            volume=100,
            wakelock=True, # Prevents the phone screen from sleeping while watching
            filter_quality=ft.FilterQuality.MEDIUM, # CRITICAL: 'HIGH' causes blurry video on Android per Flet docs
            pause_upon_entering_background_mode=True,
            resume_upon_entering_foreground_mode=True,
        )

        # A sleek, mobile-friendly back button tucked safely under the notification notch
        self.back_btn = ft.SafeArea(
            ft.Container(
                content=ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                    icon_color=ft.Colors.WHITE,
                    icon_size=22,
                    # Semi-transparent background so it's visible regardless of video color
                    bgcolor=ft.colors.with_opacity(0.4, ft.Colors.BLACK), 
                    on_click=self.handle_close,
                ),
                margin=ft.margin.only(left=15, top=10),
            )
        )

        self.controls = [
            ft.Container(expand=True, bgcolor=ft.Colors.BLACK), # Deep black base layer
            self.video,
            self.back_btn
        ]

    def handle_close(self, e):
        # PERFORMANCE: Stop the video engine immediately to dump memory before routing back
        if self.page:
            self.page.run_task(self.video.stop)
        
        if self.on_close:
            self.on_close(e)
