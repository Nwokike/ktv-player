"""Playback speed is for everything EXCEPT channels.

The rule is source-based: show_favorite is only true for channel plays,
so channels get no speed chip and everything else (local files,
downloads, deep links) always does. Duration metadata used to gate this
and was removed: some live channels report a duration, some VOD does not,
and neither says anything about whether speeding makes sense.
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


def test_speed_follows_the_source_from_construction():
    """No duration math: the source decides at open time."""
    channel = ImmersivePlayer(resource="http://example.com/live.m3u8")
    assert channel.speed_available is False, "channels never get speed"

    local = ImmersivePlayer(resource="file:///videos/movie.mp4", show_favorite=False)
    assert local.speed_available is True, "local files always get speed"

    deep_link = ImmersivePlayer(
        resource="https://example.com/stream.m3u8", show_favorite=False
    )
    assert deep_link.speed_available is True


def test_speed_chip_is_built_hidden_for_a_channel():
    from components.player.controls import build_player_controls

    player = _player(speed_available=False)
    build_player_controls(player)

    assert player.speed_container is not None
    assert player.speed_container.visible is False


def test_speed_chip_is_visible_when_available():
    from components.player.controls import build_player_controls

    player = _player(speed_available=True)
    build_player_controls(player)

    assert player.speed_container.visible is True


def test_duration_metadata_does_not_govern_speed():
    """A live channel reporting a duration must still not get speed."""
    player = _player(speed_available=False)
    player.speed_container = mock.MagicMock()
    player.update = mock.Mock()

    player._on_duration_change(SimpleNamespace(data=ft.Duration(seconds=600)))

    assert player.speed_available is False
    player.update.assert_not_called()


def test_live_stream_keeps_the_chip_hidden():
    """A live HLS playlist reports no duration at all."""
    player = _player(speed_available=False)
    player.speed_container = mock.MagicMock()
    player.speed_container.visible = False

    player._on_duration_change(SimpleNamespace(data=ft.Duration(seconds=0)))

    assert player.speed_available is False
    assert player.speed_container.visible is False  # duration never touched it


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
