import flet as ft


class GlassContainer(ft.Container):
    def __init__(
        self,
        content: ft.Control,
        padding: float = 20,
        border_radius: float = 20,
        expand: bool = False,
        on_click: callable = None,
        **kwargs,  # This allows it to accept height, width, margin, etc. safely!
    ):
        # We pass the kwargs up to the parent Flet Container
        super().__init__(**kwargs)

        self.content = content
        self.padding = padding
        self.border_radius = border_radius

        # Note: If Flet 0.84 complains about with_opacity later,
        # you can change these to Hex codes or ft.Colors.WHITE24 etc.
        self.bgcolor = ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE)
        self.border = ft.Border.all(0.5, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))

        self.blur = ft.Blur(10, 10, ft.BlurTileMode.MIRROR)
        self.expand = expand
        self.on_click = on_click
        self.animate = ft.Animation(300, ft.AnimationCurve.DECELERATE)
