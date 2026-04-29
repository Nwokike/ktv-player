import pytest
import flet as ft
from views.splash import build_splash_view


@pytest.mark.asyncio
async def test_splash_view_build():
    view = build_splash_view()
    assert isinstance(view, ft.View)
    assert view.route == "/"

    # Verify elements
    container = view.controls[0]
    column = container.content
    assert any(isinstance(c, ft.Image) for c in column.controls)
    assert any(isinstance(c, ft.ProgressBar) for c in column.controls)
    assert any(isinstance(c, ft.Text) and c.value == "KTV PLAYER" for c in column.controls)
