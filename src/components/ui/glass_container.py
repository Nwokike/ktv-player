import flet as ft


class GlassContainer(ft.Container):
    def __init__(
        self,
        content: ft.Control,
        padding: float = 20,
        border_radius: float = 20,
        expand: bool = False,
        on_click: callable = None,
        focusable: bool = False,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.content = content
        self.padding = padding
        self.border_radius = border_radius

        self._default_border = ft.Border.all(0.5, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE))
        self._focus_border = ft.Border.all(2.5, ft.Colors.PRIMARY)

        self.bgcolor = ft.Colors.with_opacity(0.06, ft.Colors.ON_SURFACE)
        self.border = self._default_border

        self.expand = expand
        self.on_click = on_click

        if focusable:
            self.tab_index = 0
            self.on_focus = self._handle_focus
            self.on_blur = self._handle_blur

    def _handle_focus(self, e):
        self.border = self._focus_border
        self.scale = 1.05
        self.update()

    def _handle_blur(self, e):
        self.border = self._default_border
        self.scale = 1.0
        self.update()
