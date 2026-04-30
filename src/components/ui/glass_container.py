import flet as ft


class GlassContainer(ft.Container):
    def __init__(
        self,
        content: ft.Control,
        padding: float = 20,
        border_radius: float = 20,
        expand: bool = False,
        on_click: callable = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.content = content
        self.padding = padding
        self.border_radius = border_radius

        self.bgcolor = ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
        self.border = ft.Border.all(0.5, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))

        self.expand = expand
        self.on_click = on_click
