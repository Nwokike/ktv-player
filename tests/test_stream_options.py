"""v2.1.0 tests: quality/audio switching via proxy pinning + PiP guards."""

from unittest import mock

import flet as ft
import pytest

from components.player.handlers import open_player_settings
from components.player.immersive_player import ImmersivePlayer


class TestResourcePinning:
    def _player(self, resource="http://example.com/stream.m3u8"):
        p = ImmersivePlayer(resource=resource, title="T")
        p.update = mock.Mock()
        return p

    def test_cannot_switch_without_proxy(self):
        p = self._player()
        assert p.can_switch_quality is False

    def test_can_switch_with_proxy_and_http_source(self):
        p = self._player()
        p.hls_proxy = mock.MagicMock()
        assert p.can_switch_quality is True

    def test_local_files_cannot_switch(self):
        p = self._player(resource="/home/user/video.mp4")
        p.hls_proxy = mock.MagicMock()
        assert p.can_switch_quality is False

    def test_pinned_variant_goes_through_proxy(self):
        p = self._player()
        proxy = mock.MagicMock()
        proxy.get_proxy_url.return_value = "http://127.0.0.1:1/pinned.m3u8"
        p.hls_proxy = proxy
        p.source_proxied = False
        assert p._resource_url_for(1, None) == "http://127.0.0.1:1/pinned.m3u8"
        proxy.get_proxy_url.assert_called_once_with(
            "http://example.com/stream.m3u8",
            referer=None,
            headers=None,
            variant=1,
            audio=None,
        )

    def test_unpinned_direct_source_stays_original(self):
        p = self._player()
        p.hls_proxy = mock.MagicMock()
        p.source_proxied = False
        assert p._resource_url_for(None, None) == "http://example.com/stream.m3u8"
        p.hls_proxy.get_proxy_url.assert_not_called()

    def test_proxied_source_always_rebuilds(self):
        p = self._player()
        proxy = mock.MagicMock()
        p.hls_proxy = proxy
        p.source_proxied = True
        p._resource_url_for(None, None)
        proxy.get_proxy_url.assert_called_once()


class TestApplyVariant:
    def _player(self):
        p = ImmersivePlayer(resource="http://example.com/stream.m3u8", title="T")
        p.update = mock.Mock()
        p.hls_proxy = mock.MagicMock()
        p.hls_proxy.get_proxy_url.return_value = "http://127.0.0.1:1/pinned.m3u8"
        p.video.get_current_position = mock.AsyncMock(
            return_value=ft.Duration(seconds=42)
        )
        p.video.get_duration = mock.AsyncMock(return_value=ft.Duration(seconds=600))
        p.video.play = mock.AsyncMock()
        p.video.seek = mock.AsyncMock()
        p.video.update = mock.Mock()
        p._start_watchdog = mock.Mock()
        return p

    @pytest.mark.asyncio
    async def test_vod_switch_restores_position(self):
        p = self._player()
        await p.apply_variant(0)
        assert p._current_variant == 0
        assert p.resource == "http://127.0.0.1:1/pinned.m3u8"
        p.video.play.assert_awaited_once()
        p.video.seek.assert_awaited_once()
        p._start_watchdog.assert_called_once()

    @pytest.mark.asyncio
    async def test_live_switch_skips_seek(self):
        p = self._player()
        p.video.get_duration = mock.AsyncMock(return_value=ft.Duration(seconds=0))
        await p.apply_variant(1)
        assert p._current_variant == 1
        p.video.seek.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_resets_pin_to_original(self):
        p = self._player()
        p.source_proxied = False
        p._current_variant = 2
        await p.apply_variant(None)
        assert p._current_variant is None
        assert p.resource == "http://example.com/stream.m3u8"

    @pytest.mark.asyncio
    async def test_apply_audio_pins_name(self):
        p = self._player()
        await p.apply_audio("Japanese")
        assert p._current_audio == "Japanese"
        p.hls_proxy.get_proxy_url.assert_called_once_with(
            "http://example.com/stream.m3u8",
            referer=None,
            headers=None,
            variant=None,
            audio="Japanese",
        )


class TestPipServiceDesktop:
    def test_pip_not_supported_without_jvm(self):
        from services import pip_service

        assert pip_service.api_level() == 0
        assert pip_service.is_pip_supported() is False
        assert pip_service.enter_pip() is False

    def test_set_auto_pip_noop_below_api_31(self):
        from services import pip_service

        assert pip_service.set_auto_pip(True) is True

    def test_player_pip_flag_false_on_desktop(self):
        p = ImmersivePlayer(resource="http://example.com/s.m3u8", title="T")
        assert p.pip_available is False


class TestSettingsDialogStreamSections:
    @pytest.mark.asyncio
    async def test_no_stream_section_in_settings(self):
        """Stream quality/audio are now in the separate quality picker (top-bar chip),
        not in the settings dialog. Settings dialog only shows snapshot preferences
        and screen aspect ratio."""
        player = mock.MagicMock()
        player.include_subtitles_in_snapshot = True
        player.snapshot_format = "image/png"
        player.can_switch_quality = True
        player._current_variant = None
        player._current_audio = None
        player.list_variants = mock.AsyncMock(
            return_value=[
                {
                    "index": 0,
                    "label": "1280x720  (2.5 Mbps)",
                    "bandwidth": 2500000,
                    "resolution": "1280x720",
                    "uri": "720/index.m3u8",
                }
            ]
        )
        player.list_audio_tracks = mock.AsyncMock(return_value=[])
        player.video = mock.MagicMock()
        player.video.fit = ft.BoxFit.CONTAIN
        player.page = mock.MagicMock()

        await open_player_settings(player)

        dialog = player.page.show_dialog.call_args[0][0]
        texts = [c.value for c in dialog.content.controls if isinstance(c, ft.Text)]
        assert "Stream" not in texts  # Stream section moved to quality picker
        assert "Snapshot Preferences" in texts
        assert "Screen Aspect Ratio" in texts
