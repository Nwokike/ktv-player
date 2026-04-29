import flet as ft
from components.ui.glass_container import GlassContainer


def test_glass_container_init():
    content = ft.Text("Hello")
    glass = GlassContainer(content=content, padding=10, height=100)

    assert glass.content == content
    assert glass.padding == 10
    assert glass.height == 100
    assert glass.blur.sigma_x == 10
    assert glass.animate is not None
