import flet as ft


class ShimmerList(ft.Column):
    def __init__(self, count: int = 5):
        super().__init__()
        self.count = count
        self.spacing = 10
        self.controls = [self.build_shimmer_item() for _ in range(count)]

    def build_shimmer_item(self):
        return ft.Container(
            height=60,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=10,
            animate_opacity=ft.Animation(1000, ft.AnimationCurve.EASE_IN_OUT),
        )

    def did_mount(self):
        # We can add a simple pulse animation if we want
        pass
