"""Tests for player handler logic."""

import asyncio
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
        player.page = mock.MagicMock()

        handle_stream_complete(player, mock.MagicMock())

        assert player._reconnect_count == 1
        player._show_progress.assert_called_once_with("Reconnecting stream (1/5)...")
        assert player.page.run_task.called

    def test_handle_stream_complete_reconnects_for_https(self):
        """HTTPS streams should also trigger reconnection."""
        player = mock.MagicMock()
        player.resource = "https://cdn.example.com/stream"
        player._reconnect_count = 0
        player.page = mock.MagicMock()

        handle_stream_complete(player, mock.MagicMock())

        assert player._reconnect_count == 1
        player._show_progress.assert_called_once()

    def test_handle_stream_complete_shows_error_after_max_reconnects(self):
        """After STREAM_RECONNECT_MAX attempts, show final error instead."""
        player = mock.MagicMock()
        player.resource = "http://example.com/stream"
        player._reconnect_count = 5  # STREAM_RECONNECT_MAX = 5
        player.page = mock.MagicMock()

        handle_stream_complete(player, mock.MagicMock())

        assert player._show_final_error.called
        assert not player.page.run_task.called


class TestReconnectStream:
    """Tests for reconnect_stream -- actual reconnection logic."""

    @pytest.mark.asyncio
    async def test_reconnect_stream_resets_playlist_and_plays(self):
        """reconnect_stream should re-create the playlist, call play() and
        arm the watchdog so a silent stall still resolves."""
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
        player._start_watchdog.assert_called_once()

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


class TestPlaybackStatesAndWatchdog:
    """Real ImmersivePlayer: overlay states, watchdog guarantees, retry."""

    def _player(self):
        from components.player.immersive_player import ImmersivePlayer

        p = ImmersivePlayer(resource="http://example.com/stream.m3u8", title="T")
        p.update = mock.Mock()
        return p

    def test_show_progress_shows_back_and_hides_retry(self):
        p = self._player()
        p._show_progress("Connecting...")
        assert p.status_text.value == "Connecting..."
        assert p.loading_ring.visible is True
        assert p.overlay.visible is True
        assert p.error_actions_row.visible is True
        assert p.back_error_btn.visible is True
        assert p.retry_btn.visible is False
        assert p.overlay.on_click is not None  # tap-to-close escape

    def test_final_error_shows_both_buttons(self):
        p = self._player()
        p._show_final_error("nope")
        assert p.status_text.value == "nope"
        assert p.loading_ring.visible is False
        assert p.retry_btn.visible is True
        assert p.back_error_btn.visible is True

    def test_network_timeout_configured_on_video(self):
        """mpv network-timeout must be set — the 60s default let dead hosts
        spin the loader forever without an error event."""
        p = self._player()
        props = p.video.configuration.mpv_properties or {}
        assert props.get("network-timeout") == 10

    @pytest.mark.asyncio
    async def test_watchdog_fires_when_stalled(self):
        p = self._player()
        p._show_final_error = mock.Mock()
        p._show_progress("Loading stream...")
        p._start_watchdog(timeout=0.05)
        await asyncio.sleep(0.12)
        p._show_final_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_watchdog_cancelled_on_success(self):
        p = self._player()
        p._show_final_error = mock.Mock()
        p._show_progress("Loading stream...")
        p._start_watchdog(timeout=0.05)
        p._hide_overlay()  # on_load / first position tick
        await asyncio.sleep(0.12)
        p._show_final_error.assert_not_called()

    @pytest.mark.asyncio
    async def test_watchdog_cancelled_on_final_error(self):
        p = self._player()
        p._show_progress("Loading stream...")
        p._start_watchdog(timeout=0.05)
        # A real error arrives before the watchdog fires
        p._show_final_error("Unable to load stream.")
        assert p._is_final_error is True
        assert p._watchdog_task is None  # cancelled and cleared

    @pytest.mark.asyncio
    async def test_manual_retry_resets_state_and_arms_watchdog(self):
        p = self._player()
        p._reconnect_count = 4
        p._is_final_error = True
        p.video.play = mock.AsyncMock()
        p.video.update = mock.Mock()
        p._start_watchdog = mock.Mock()
        await p._manual_retry()
        assert p._reconnect_count == 0
        assert p._is_final_error is False
        assert p.back_error_btn.visible is True  # escape stays during retry
        p._start_watchdog.assert_called_once()

    @pytest.mark.asyncio
    async def test_manual_retry_error_shows_buttons_again(self):
        p = self._player()
        p.video.play = mock.AsyncMock(side_effect=Exception("boom"))
        p._start_watchdog = mock.Mock()
        await p._manual_retry()
        assert p._is_final_error is True
        assert p.retry_btn.visible is True
        assert p.back_error_btn.visible is True
        p._start_watchdog.assert_not_called()
