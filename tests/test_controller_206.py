"""Controller-level tests for 2.0.6: offline wording + liveliness reset,
and deep-link plays hiding the in-player favorite star while STILL saving
history (Recently Watched behavior is intentionally untouched)."""

from unittest import mock

import pytest
from flet import ConnectivityType

import main as main_mod
from core.constants import MSG_OFFLINE, MSG_ONLINE
from core.state import state
from services.liveliness import liveliness_cache


@pytest.fixture(autouse=True)
def _reset_state():
    state.reset()
    liveliness_cache.clear()
    yield
    state.reset()
    liveliness_cache.clear()


class TestConnectivityChange:
    def test_going_offline_clears_liveliness_cache(self, fake_page):
        liveliness_cache.set("http://x/live", True)
        controller = main_mod.AppController(fake_page)
        e = mock.MagicMock()
        e.connectivity = [ConnectivityType.NONE]
        controller._on_connectivity_change(e)
        assert state.is_online is False
        assert liveliness_cache.get("http://x/live") is None  # dot back to neutral

    def test_offline_message_mentions_local_videos(self, fake_page):
        controller = main_mod.AppController(fake_page)
        with mock.patch("utils.notifications.notify_warning") as warn:
            e = mock.MagicMock()
            e.connectivity = [ConnectivityType.NONE]
            controller._on_connectivity_change(e)
        warn.assert_called_once_with(MSG_OFFLINE, persist=True)
        assert "Local videos" in MSG_OFFLINE

    def test_coming_online_notifies(self, fake_page):
        state.is_online = False
        controller = main_mod.AppController(fake_page)
        with mock.patch("utils.notifications.notify") as ok:
            e = mock.MagicMock()
            e.connectivity = [ConnectivityType.WIFI]
            controller._on_connectivity_change(e)
        assert state.is_online is True
        ok.assert_called_once_with(MSG_ONLINE)


class TestDeepLinkFavorite:
    @pytest.mark.asyncio
    async def test_deep_link_hides_fav_but_saves_history(self, fake_page):
        with mock.patch.object(main_mod, "db_manager") as db:
            db.save_history = mock.AsyncMock()
            controller = main_mod.AppController(fake_page)
            await controller.play_stream(
                "http://anime.example/ep1.m3u8", None, from_deep_link=True
            )
            player = main_mod.AppController._find_immersive_player(
                fake_page.views[-1].controls[0]
            )
            assert player is not None
            assert player.show_favorite_button is False
            # History is saved for deep-link plays too (recently watched untouched)
            assert state.history[0]["url"] == "http://anime.example/ep1.m3u8"
            db.save_history.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_in_app_play_shows_fav(self, fake_page):
        with mock.patch.object(main_mod, "db_manager") as db:
            db.save_history = mock.AsyncMock()
            controller = main_mod.AppController(fake_page)
            await controller.play_stream("http://tv.example/live.m3u8", None)
            player = main_mod.AppController._find_immersive_player(
                fake_page.views[-1].controls[0]
            )
            assert player is not None
            assert player.show_favorite_button is True


class TestLocalVideoFavorite:
    @pytest.mark.asyncio
    async def test_local_video_hides_fav_but_saves_history(self, fake_page):
        with mock.patch.object(main_mod, "db_manager") as db:
            db.save_history = mock.AsyncMock()
            controller = main_mod.AppController(fake_page)
            await controller.play_stream("/home/user/Downloads/movie.mp4", None)
            player = main_mod.AppController._find_immersive_player(
                fake_page.views[-1].controls[0]
            )
            assert player is not None
            assert player.show_favorite_button is False
            # Local videos still land in history (Recently Watched untouched)
            assert state.history[0]["url"] == "/home/user/Downloads/movie.mp4"
            db.save_history.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_content_uri_hides_fav(self, fake_page):
        with mock.patch.object(main_mod, "db_manager") as db:
            db.save_history = mock.AsyncMock()
            controller = main_mod.AppController(fake_page)
            await controller.play_stream("content://media/video/12", None)
            player = main_mod.AppController._find_immersive_player(
                fake_page.views[-1].controls[0]
            )
            assert player is not None
            assert player.show_favorite_button is False
