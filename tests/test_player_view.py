import pytest
from unittest.mock import MagicMock
import flet as ft
from views.player_view import build_player_view
from components.player.immersive_player import ImmersivePlayer


@pytest.mark.asyncio
async def test_player_view_build():
    on_back = MagicMock()
    view = build_player_view("http://test.com/stream.m3u8", on_back)
    assert isinstance(view, ft.View)
    assert view.route == "/play?url=http://test.com/stream.m3u8"

    # Check if ImmersivePlayer is in the view
    container = view.controls[0]
    assert isinstance(container.content, ImmersivePlayer)


@pytest.mark.asyncio
async def test_immersive_player_init():
    on_close = MagicMock()
    player = ImmersivePlayer("url1", on_close)
    assert player.resource == "url1"
    assert len(player.controls) == 3  # Black background, Video, Back button


@pytest.mark.asyncio
async def test_player_close_callback():
    on_close = MagicMock()
    player = ImmersivePlayer("url1", on_close)

    # Simulate back button click
    player.handle_close(MagicMock())
    on_close.assert_called_once()


@pytest.mark.asyncio
async def test_player_close_callback_no_args():
    # Test callback that doesn't accept event arg
    on_close = MagicMock()
    # Mock to fail with TypeError when called with 1 arg
    on_close.side_effect = [TypeError, None]

    player = ImmersivePlayer("url1", on_close)
    player.handle_close(MagicMock())

    assert on_close.call_count == 2  # Once with arg (failed), once without
