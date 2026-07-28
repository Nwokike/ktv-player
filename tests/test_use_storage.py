"""Tests for the use_storage async facade over database.manager.db_manager."""

from unittest import mock

import pytest

from app_next.hooks.use_storage import Storage, use_storage


@pytest.mark.anyio
async def test_use_storage_returns_a_storage_instance():
    storage = use_storage()
    assert isinstance(storage, Storage)


@pytest.mark.anyio
async def test_set_setting_delegates_to_db_manager():
    storage = use_storage()
    with mock.patch("app_next.hooks.use_storage.db_manager") as dbm:
        dbm.set_setting = mock.AsyncMock()
        await storage.set_setting("user_country", "Nigeria")
        dbm.set_setting.assert_awaited_once_with("user_country", "Nigeria")


@pytest.mark.anyio
async def test_get_setting_delegates_to_db_manager():
    storage = use_storage()
    with mock.patch("app_next.hooks.use_storage.db_manager") as dbm:
        dbm.get_setting = mock.AsyncMock(return_value="Nigeria")
        result = await storage.get_setting("user_country")
        dbm.get_setting.assert_awaited_once_with("user_country", default=None)
        assert result == "Nigeria"


@pytest.mark.anyio
async def test_get_setting_passes_default_through():
    storage = use_storage()
    with mock.patch("app_next.hooks.use_storage.db_manager") as dbm:
        dbm.get_setting = mock.AsyncMock(return_value="fallback")
        await storage.get_setting("missing", default="fallback")
        dbm.get_setting.assert_awaited_once_with("missing", default="fallback")
