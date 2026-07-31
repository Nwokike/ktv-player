"""Tests for the use_storage async facade over database.manager.db_manager."""

from unittest import mock

import pytest

from hooks.use_storage import Storage, use_storage


@pytest.mark.anyio
async def test_use_storage_returns_a_storage_instance():
    storage = use_storage()
    assert isinstance(storage, Storage)


@pytest.mark.anyio
async def test_set_setting_delegates_to_db_manager():
    storage = use_storage()
    with mock.patch("hooks.use_storage.db_manager") as dbm:
        dbm.set_setting = mock.AsyncMock()
        await storage.set_setting("user_country", "Nigeria")
        dbm.set_setting.assert_awaited_once_with("user_country", "Nigeria")


@pytest.mark.anyio
async def test_get_setting_delegates_to_db_manager():
    storage = use_storage()
    with mock.patch("hooks.use_storage.db_manager") as dbm:
        dbm.get_setting = mock.AsyncMock(return_value="Nigeria")
        result = await storage.get_setting("user_country")
        dbm.get_setting.assert_awaited_once_with("user_country", default=None)
        assert result == "Nigeria"


@pytest.mark.anyio
async def test_get_setting_passes_default_through():
    storage = use_storage()
    with mock.patch("hooks.use_storage.db_manager") as dbm:
        dbm.get_setting = mock.AsyncMock(return_value="fallback")
        await storage.get_setting("missing", default="fallback")
        dbm.get_setting.assert_awaited_once_with("missing", default="fallback")


@pytest.mark.anyio
async def test_add_playlist_and_custom_channel_delegates():
    storage = use_storage()
    assert storage.db_manager is not None
    with mock.patch("hooks.use_storage.db_manager") as dbm:
        dbm.add_playlist = mock.AsyncMock()
        dbm.add_custom_channel = mock.AsyncMock()

        await storage.add_playlist("Test Playlist", "http://example.com/m3u")
        dbm.add_playlist.assert_awaited_once_with(
            "Test Playlist", "http://example.com/m3u"
        )

        await storage.add_custom_channel("Test Channel", "http://example.com/stream")
        dbm.add_custom_channel.assert_awaited_once_with(
            "Test Channel", "http://example.com/stream"
        )
