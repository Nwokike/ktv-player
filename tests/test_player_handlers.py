"""Tests for player handler logic."""

import asyncio
import types
from unittest import mock

import flet as ft
import pytest

from components.player.handlers import (
    cycle_speed,
    handle_stream_complete,
    open_player_settings,
    open_quality_picker,
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
        player.speed_texts = [player.speed_text]
        # Bind the REAL _branch_controls: AsyncMock turns every method call
        # into a coroutine, and the handler iterates its return value.
        from components.player.immersive_player import ImmersivePlayer

        player._branch_controls = types.MethodType(
            ImmersivePlayer._branch_controls, player
        )

        await cycle_speed(player)

        assert player._speed_idx == 3
        assert player.video.playback_rate == 1.25
        assert player.speed_text.value == "1.25x"
        # Single update: speed_text lives inside video.controls, so
        # video.update() already pushes it (no child .update() storm).
        player.video.update.assert_called_once()
        player.speed_text.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_cycle_speed_wraps_around(self):
        """Cycling past the last speed should wrap to the first."""
        player = mock.AsyncMock()
        player._speed_idx = 5
        player._speeds = [0.25, 0.5, 1.0, 1.25, 1.5, 2.0]
        player.video = mock.MagicMock()
        player.speed_text = mock.MagicMock()
        player.speed_texts = [player.speed_text]
        # Bind the REAL _branch_controls: AsyncMock turns every method call
        # into a coroutine, and the handler iterates its return value.
        from components.player.immersive_player import ImmersivePlayer

        player._branch_controls = types.MethodType(
            ImmersivePlayer._branch_controls, player
        )

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
        player.speed_texts = [player.speed_text]
        from components.player.immersive_player import ImmersivePlayer

        player._branch_controls = types.MethodType(
            ImmersivePlayer._branch_controls, player
        )

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
        # Mirror the real player: safe_page resolves to page when mounted.
        player.safe_page = player.page

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
        # Await the watchdog task itself — deterministic, no sleep margin.
        await asyncio.wait_for(asyncio.shield(p._watchdog_task), timeout=2)
        p._show_final_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_watchdog_cancelled_on_success(self):
        p = self._player()
        p._show_final_error = mock.Mock()
        p._show_progress("Loading stream...")
        p._start_watchdog(timeout=0.05)
        task = p._watchdog_task
        p._hide_overlay()  # on_load / first position tick
        # Cancellation is synchronous: no sleep needed.
        assert p._watchdog_task is None
        await asyncio.gather(task, return_exceptions=True)
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


class TestVodResumeAndPositionTracking:
    def _player(self, source_url="http://example.com/vod.mp4"):
        from components.player.immersive_player import ImmersivePlayer

        p = ImmersivePlayer(resource=source_url, source_url=source_url, title="T")
        p.update = mock.Mock()
        return p

    @pytest.mark.asyncio
    async def test_save_current_position_vod(self):
        from database.manager import db_manager

        p = self._player("http://example.com/movie.mp4")
        p.video.get_current_position = mock.AsyncMock(
            return_value=ft.Duration(seconds=150)
        )
        p.video.get_duration = mock.AsyncMock(return_value=ft.Duration(seconds=600))
        with mock.patch.object(
            db_manager, "update_history_position", new_callable=mock.AsyncMock
        ) as mock_update:
            await p._save_current_position()
            mock_update.assert_awaited_once_with(
                "http://example.com/movie.mp4", 150.0, 600.0
            )

    @pytest.mark.asyncio
    async def test_skip_save_position_live(self):
        from database.manager import db_manager

        p = self._player("http://example.com/live.m3u8")
        p.video.get_current_position = mock.AsyncMock(
            return_value=ft.Duration(seconds=150)
        )
        p.video.get_duration = mock.AsyncMock(return_value=ft.Duration(seconds=0))
        with mock.patch.object(
            db_manager, "update_history_position", new_callable=mock.AsyncMock
        ) as mock_update:
            await p._save_current_position()
            mock_update.assert_not_called()

    @pytest.mark.asyncio
    async def test_completion_resets_position(self):
        from components.player.immersive_player import _orphan_tasks
        from database.manager import db_manager

        p = self._player("http://example.com/movie.mp4")
        p._last_duration = 600.0
        with mock.patch.object(
            db_manager, "update_history_position", new_callable=mock.AsyncMock
        ) as mock_update:
            p._on_complete(mock.MagicMock())
            # The reset rides the tracked orphan task — join it, no sleep.
            pending = [t for t in list(_orphan_tasks)]
            if pending:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True), timeout=2
                )
            mock_update.assert_called_with("http://example.com/movie.mp4", 0.0, 600.0)


class TestCompleteGateAndReconnect:
    """Phase 2: _is_final_error gate, reconnect reapply, non-HTTP path."""

    def test_complete_gated_on_final_error(self):
        """No 'Reconnecting' over a dead-error overlay."""
        player = mock.MagicMock()
        player.resource = "http://example.com/stream"
        player._is_final_error = True
        player._last_duration = 600.0
        player._last_position = 100.0

        handle_stream_complete(player, mock.MagicMock())

        player._show_progress.assert_not_called()
        player._show_final_error.assert_not_called()

    def test_complete_ignores_mock_final_error(self):
        """Unset (MagicMock auto-attr) must not gate: only `is True` gates."""
        player = mock.MagicMock()
        player.resource = "http://example.com/stream"
        player._reconnect_count = 0
        player._last_duration = 600.0
        player._last_position = 100.0
        player.page = mock.MagicMock()
        player.safe_page = player.page
        del player._is_final_error  # getattr(..., False) default path

        handle_stream_complete(player, mock.MagicMock())

        assert player._reconnect_count == 1

    def test_non_http_complete_shows_final_error(self):
        """Local files can't reconnect: explicit error, not black screen."""
        player = mock.MagicMock()
        player.resource = "/storage/video.mp4"
        player._last_duration = 600.0
        player._last_position = 100.0

        handle_stream_complete(player, mock.MagicMock())

        player._show_final_error.assert_called_once_with("Playback ended.")

    @pytest.mark.asyncio
    async def test_reconnect_reapplies_rate_and_resets_count(self):
        """Reconnect restores speed and resets the counter on success."""
        player = mock.MagicMock()
        player._is_closing = False
        player.resource = "http://example.com/stream"
        player.http_headers = {}
        player._speeds = [0.25, 0.5, 1.0]
        player._speed_idx = 2
        player._reconnect_count = 3
        player.video = mock.MagicMock()
        player.video.play = mock.AsyncMock()
        player._start_watchdog = mock.MagicMock()

        await reconnect_stream(player)

        assert player.video.playback_rate == 1.0
        assert player._reconnect_count == 0
        player._start_watchdog.assert_called_once()


class TestAudioProbeUnconditional:
    """Phase 2: single-variant streams still show audio options."""

    @pytest.mark.asyncio
    async def test_quality_picker_shows_audio_without_variants(self):
        """Tracks fetched even when variants list is empty."""
        player = mock.MagicMock()
        player._current_variant = None
        player._current_audio = None
        player.list_variants = mock.AsyncMock(return_value=[])
        player.list_audio_tracks = mock.AsyncMock(
            return_value=[
                {"name": "eng", "language": "English"},
                {"name": "spa", "language": "Spanish"},
            ]
        )
        player.page = mock.MagicMock()

        await open_quality_picker(player)

        player.list_audio_tracks.assert_awaited_once()
        dialog = player.page.show_dialog.call_args[0][0]
        # Auto quality + Divider + Audio header + Default + 2 tracks.
        assert len(dialog.content.content.controls) == 6
        titles = [
            c.title.value
            for c in dialog.content.content.controls
            if isinstance(c, ft.ListTile) and isinstance(c.title, ft.Text)
        ]
        assert "eng (English)" in titles
        assert "spa (Spanish)" in titles


class TestSubtitleSizeControl:
    """Phase 2: subtitle size dropdown persists and applies."""

    @pytest.mark.asyncio
    async def test_settings_dialog_has_subtitle_size(self):
        """Player settings include a Subtitle Size dropdown (default medium)."""
        from database.manager import db_manager

        player = mock.MagicMock()
        player.include_subtitles_in_snapshot = True
        player.snapshot_format = "image/png"
        player.can_switch_quality = False
        player._current_variant = None
        player._current_audio = None
        player._variants_cache = []
        player._audio_tracks_cache = []
        player.list_variants = mock.AsyncMock(return_value=[])
        player.list_audio_tracks = mock.AsyncMock(return_value=[])
        player.video = mock.MagicMock()
        player.video.fit = ft.BoxFit.CONTAIN
        player.page = mock.MagicMock()
        player.page.run_task = mock.MagicMock()
        # Pre-seed a stored size so the dialog reflects persistence.
        await db_manager.set_setting("subtitle_size", "large")

        await open_player_settings(player)

        dialog = player.page.show_dialog.call_args[0][0]
        size_dd = next(
            c
            for c in dialog.content.controls
            if getattr(c, "label", None) == "Subtitle Size"
        )
        assert size_dd.value == "large"
        await db_manager.set_setting("subtitle_size", "medium")

    def test_subtitle_size_map(self):
        from components.player.immersive_player import ImmersivePlayer

        assert ImmersivePlayer._SUBTITLE_SIZES == {
            "small": 16.0,
            "medium": 22.0,
            "large": 30.0,
        }
