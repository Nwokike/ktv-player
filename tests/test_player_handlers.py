"""Tests for player handler logic."""

from unittest import mock

import pytest

from components.player.handlers import (
    cycle_speed,
    handle_stream_complete,
    reconnect_stream,
)


class TestCycleSpeed:
    """Tests for cycle_speed -- playback speed cycling."""

    @pytest.mark.asyncio
    async def test_cycle_speed_advances_through_speeds(self):
        """Calling cycle_speed should advance _speed_idx and update the player."""
        player = mock.AsyncMock()
        player._speed_idx = 2
        player._speeds = [0.25, 0.5, 1.0, 1.25, 1.5, 2.0]
        player.video = mock.MagicMock()
        player.speed_text = mock.MagicMock()

        await cycle_speed(player)

        assert player._speed_idx == 3
        assert player.video.playback_rate == 1.25
        assert player.speed_text.value == "1.25x"
        assert player.video.update.called
        assert player.speed_text.update.called

    @pytest.mark.asyncio
    async def test_cycle_speed_wraps_around(self):
        """Cycling past the last speed should wrap to the first."""
        player = mock.AsyncMock()
        player._speed_idx = 5
        player._speeds = [0.25, 0.5, 1.0, 1.25, 1.5, 2.0]
        player.video = mock.MagicMock()
        player.speed_text = mock.MagicMock()

        await cycle_speed(player)

        assert player._speed_idx == 0
        assert player.video.playback_rate == 0.25
        assert player.speed_text.value == "0.25x"

    @pytest.mark.asyncio
    async def test_cycle_speed_handles_update_failure_gracefully(self):
        """cycle_speed should not raise if video.update() fails."""
        player = mock.AsyncMock()
        player._speed_idx = 2
        player._speeds = [0.25, 0.5, 1.0, 1.25, 1.5, 2.0]
        player.video = mock.MagicMock()
        player.video.update.side_effect = Exception("UI gone")
        player.speed_text = mock.MagicMock()

        # Must not raise
        await cycle_speed(player)

        assert player._speed_idx == 3


class TestHandleStreamComplete:
    """Tests for handle_stream_complete -- stream reconnection logic."""

    def test_handle_stream_complete_triggers_reconnect_for_http(self):
        """HTTP streams should trigger reconnection via run_task."""
        player = mock.MagicMock()
        player.resource = "http://example.com/stream"
        player._reconnect_count = 0
        player._overlay_hidden = True
        player.status_text = mock.MagicMock()
        player.loading_ring = mock.MagicMock()
        player.overlay = mock.MagicMock()
        player.page = mock.MagicMock()

        handle_stream_complete(player, mock.MagicMock())

        assert player._reconnect_count == 1
        assert player._overlay_hidden is False
        assert player.loading_ring.visible is True
        assert player.overlay.visible is True
        assert player.page.run_task.called

    def test_handle_stream_complete_reconnects_for_https(self):
        """HTTPS streams should also trigger reconnection."""
        player = mock.MagicMock()
        player.resource = "https://cdn.example.com/stream"
        player._reconnect_count = 0
        player._overlay_hidden = True
        player.status_text = mock.MagicMock()
        player.loading_ring = mock.MagicMock()
        player.overlay = mock.MagicMock()
        player.page = mock.MagicMock()

        handle_stream_complete(player, mock.MagicMock())

        assert player._reconnect_count == 1
        assert player._enable_tap_to_close.called

    def test_handle_stream_complete_shows_error_after_max_reconnects(self):
        """After STREAM_RECONNECT_MAX attempts, show final error instead."""
        player = mock.MagicMock()
        player.resource = "http://example.com/stream"
        player._reconnect_count = 5  # STREAM_RECONNECT_MAX = 5
        player.status_text = mock.MagicMock()
        player.loading_ring = mock.MagicMock()
        player.overlay = mock.MagicMock()
        player.page = mock.MagicMock()

        handle_stream_complete(player, mock.MagicMock())

        assert player._show_final_error.called
        assert not player.page.run_task.called


class TestReconnectStream:
    """Tests for reconnect_stream -- actual reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnect_stream_resets_playlist_and_plays(self):
        """reconnect_stream should re-create the playlist and call play()."""
        player = mock.MagicMock()
        player._is_closing = False
        player.video = mock.MagicMock()
        player.video.play = mock.AsyncMock()
        player.resource = "http://example.com/stream"
        player.http_headers = {}

        await reconnect_stream(player)

        assert player.video.playlist is not None
        assert player.video.update.called
        assert player.video.play.called

    @pytest.mark.asyncio
    async def test_reconnect_stream_skips_when_closing(self):
        """reconnect_stream should do nothing if the player is closing."""
        player = mock.MagicMock()
        player._is_closing = True
        player.video = mock.MagicMock()

        await reconnect_stream(player)

        assert not player.video.play.called

    @pytest.mark.asyncio
    async def test_reconnect_stream_shows_error_on_failure(self):
        """If play() fails, reconnect_stream should show final error."""
        player = mock.MagicMock()
        player._is_closing = False
        player.video = mock.MagicMock()
        player.video.play = mock.AsyncMock(side_effect=Exception("Playback failed"))
        player.resource = "http://example.com/stream"
        player.http_headers = {}

        await reconnect_stream(player)

        assert player._show_final_error.called
