"""Playback speed is a VOD/local feature — never a live one.

The inverse of favorites (which are offered only for channels): the user
noticed this after adding downloads and speeding up a live channel, where
there is no seekable timeline to speed up.
"""

from types import SimpleNamespace
from unittest import mock

import flet as ft
import pytest

from components.player.handlers import cycle_speed
from components.player.immersive_player import ImmersivePlayer


def _player(speed_available: bool = False):
    player = ImmersivePlayer(resource="http://example.com/live.m3u8")
    player._overlay_hidden = True
    player._check_and_trigger_seek = lambda: None
    player.speed_available = speed_available
    # `page` is a read-only property; safe_page() honours _mock_page.
    player._mock_page = mock.MagicMock()
    return player


def test_speed_chip_is_built_hidden_until_duration_arrives():
    from components.player.controls import build_player_controls

    player = _player(speed_available=False)
    build_player_controls(player)

    assert player.speed_container is not None
    assert player.speed_container.visible is False


def test_speed_chip_is_visible_for_content_with_duration():
    from components.player.controls import build_player_controls

    player = _player(speed_available=True)
    build_player_controls(player)

    assert player.speed_container.visible is True


def test_duration_metadata_reveals_the_chip():
    player = _player(speed_available=False)
    player.speed_container = mock.MagicMock()
    player.update = mock.Mock()

    player._on_duration_change(SimpleNamespace(data=ft.Duration(seconds=600)))

    assert player.speed_available is True
    player.speed_container.visible = True
    player.update.assert_called()


def test_live_stream_keeps_the_chip_hidden():
    """A live HLS playlist reports no duration at all."""
    player = _player(speed_available=False)
    player.speed_container = mock.MagicMock()

    player._on_duration_change(SimpleNamespace(data=ft.Duration(seconds=0)))

    assert player.speed_available is False
    player.speed_container.visible = not True  # never touched


@pytest.mark.asyncio
async def test_cycle_speed_refuses_on_live():
    player = _player(speed_available=False)
    player.video = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    with mock.patch("utils.notifications.notify") as notify:
        await cycle_speed(player)

    # No rate change and no text churn — and the user is told why.
    assert not isinstance(player.video.playback_rate, float)
    assert notify.called, "the user should be told why nothing happened"


@pytest.mark.asyncio
async def test_cycle_speed_changes_rate_for_vod():
    player = _player(speed_available=True)
    player.video = mock.MagicMock()
    player.speed_text = mock.MagicMock()
    player.speed_text.value = "1.0x"

    await cycle_speed(player)

    assert player.video.playback_rate in player._speeds
