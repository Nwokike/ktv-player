"""Tests for DatabaseManager and state synchronization."""

import pytest

from core.state import AppState
from database.manager import DatabaseManager


@pytest.fixture
def temp_db(tmp_path):
    """Create a DatabaseManager with a temp file."""
    db = DatabaseManager(storage_path=tmp_path)
    return db


class TestDatabaseManager:
    """Tests for the data persistence layer."""

    @pytest.mark.asyncio
    async def test_init_db_creates_empty_data(self, temp_db):
        await temp_db.init_db()
        assert temp_db._data is not None

    @pytest.mark.asyncio
    async def test_set_and_get_setting(self, temp_db):
        await temp_db.init_db()
        await temp_db.set_setting("user_country", "Nigeria")
        result = await temp_db.get_setting("user_country")
        assert result == "Nigeria"

    @pytest.mark.asyncio
    async def test_get_setting_default(self, temp_db):
        await temp_db.init_db()
        result = await temp_db.get_setting("nonexistent", default="fallback")
        assert result == "fallback"

    @pytest.mark.asyncio
    async def test_add_and_remove_favorite(self, temp_db):
        await temp_db.init_db()
        await temp_db.add_favorite("http://test.com", "Test")
        urls = await temp_db.get_favorite_urls()
        assert "http://test.com" in urls
        await temp_db.remove_favorite("http://test.com")
        urls = await temp_db.get_favorite_urls()
        assert "http://test.com" not in urls

    @pytest.mark.asyncio
    async def test_save_and_get_history(self, temp_db):
        await temp_db.init_db()
        await temp_db.save_history("http://hist.com")
        history = await temp_db.get_history()
        assert "http://hist.com" in history

    @pytest.mark.asyncio
    async def test_clear_history(self, temp_db):
        await temp_db.init_db()
        await temp_db.save_history("http://hist.com")
        await temp_db.clear_history()
        history = await temp_db.get_history()
        assert history == []

    @pytest.mark.asyncio
    async def test_add_custom_channel(self, temp_db):
        await temp_db.init_db()
        await temp_db.add_custom_channel("My Channel", "http://my.channel")
        channels = await temp_db.get_custom_channels()
        assert any(c["name"] == "My Channel" for c in channels)

    @pytest.mark.asyncio
    async def test_persistence_across_reload(self, temp_db):
        await temp_db.init_db()
        await temp_db.set_setting("persist_test", "saved")

        # Re-init (simulates app restart)
        temp_db2 = DatabaseManager(storage_path=temp_db.storage_dir)
        await temp_db2.init_db()
        result = await temp_db2.get_setting("persist_test")
        assert result == "saved"

    @pytest.mark.asyncio
    async def test_corrupt_file_handling(self, temp_db):
        # Write corrupt data
        temp_db.storage_file.write_bytes(b"not json{{{")
        await temp_db.init_db()
        # Should have loaded empty data or recovered from backup
        assert temp_db._data is not None

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, temp_db):
        import asyncio

        await temp_db.init_db()

        async def write_a():
            for i in range(5):
                await temp_db.set_setting(f"key_a_{i}", f"val_a_{i}")

        async def write_b():
            for i in range(5):
                await temp_db.set_setting(f"key_b_{i}", f"val_b_{i}")

        await asyncio.gather(write_a(), write_b())
        # Both sets of keys should exist
        for i in range(5):
            assert await temp_db.get_setting(f"key_a_{i}") == f"val_a_{i}"
            assert await temp_db.get_setting(f"key_b_{i}") == f"val_b_{i}"


class TestAppState:
    """Tests for AppState synchronization with DB."""

    def test_state_synchronization(self):
        state = AppState()
        state.reset()
        assert state.favorites == []
        assert state.history == []
        assert state.is_first_launch is True

    def test_add_to_history_dedup(self):
        state = AppState()
        state.reset()
        state.add_to_history("http://a")
        state.add_to_history("http://b")
        state.add_to_history("http://a")  # duplicate
        assert state.history[0] == "http://a"  # moved to front
        assert len(state.history) == 2

    def test_set_channels(self):
        state = AppState()
        state.reset()
        channels = [{"url": "http://1"}, {"url": "http://2"}]
        state.set_channels(channels)
        assert len(state.channels) == 2
        # Verify it's a copy (not same reference)
        channels.append({"url": "http://3"})
        assert len(state.channels) == 2
