import pytest
import os
import aiosqlite
from database.manager import DatabaseManager


@pytest.fixture
async def db_manager():
    db_path = "test_ktv_main.db"
    manager = DatabaseManager(db_path)
    await manager.init_db()
    yield manager
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.mark.asyncio
async def test_history_persistence(db_manager):
    test_url = "http://example.com/stream.m3u8"
    await db_manager.save_history(test_url)
    history = await db_manager.get_history()
    assert test_url in history


@pytest.mark.asyncio
async def test_settings_persistence(db_manager):
    await db_manager.set_setting("user_country", "Nigeria")
    val = await db_manager.get_setting("user_country")
    assert val == "Nigeria"

    # Test default value
    val_default = await db_manager.get_setting("non_existent", "default_val")
    assert val_default == "default_val"


@pytest.mark.asyncio
async def test_playlist_management(db_manager):
    await db_manager.add_playlist("Test Playlist", "http://example.com/playlist.m3u")
    playlists = await db_manager.get_playlists()

    assert len(playlists) == 1
    assert playlists[0]["name"] == "Test Playlist"
    assert playlists[0]["url"] == "http://example.com/playlist.m3u"
    assert playlists[0]["is_active"] == 1


@pytest.mark.asyncio
async def test_custom_channel_management(db_manager):
    await db_manager.add_custom_channel("Single Channel", "http://test.com/stream.m3u8", "My Group")
    channels = await db_manager.get_custom_channels()

    assert len(channels) == 1
    assert channels[0]["name"] == "Single Channel"
    assert channels[0]["group"] == "My Group"


@pytest.mark.asyncio
async def test_wal_mode(db_manager):
    async with aiosqlite.connect(db_manager.db_path) as db:
        async with db.execute("PRAGMA journal_mode") as cursor:
            row = await cursor.fetchone()
            assert row[0].upper() == "WAL"


@pytest.mark.asyncio
async def test_clear_data(db_manager):
    # Setup data
    await db_manager.save_history("url1")
    await db_manager.add_playlist("P1", "url_p1")
    await db_manager.add_custom_channel("C1", "url_c1")

    # Clear history
    await db_manager.clear_history()
    history = await db_manager.get_history()
    assert len(history) == 0

    # Clear custom content
    await db_manager.clear_custom_content()
    playlists = await db_manager.get_playlists()
    channels = await db_manager.get_custom_channels()
    assert len(playlists) == 0
    assert len(channels) == 0


@pytest.mark.asyncio
async def test_init_db_creates_dir():
    # Use a nested path to test directory creation
    db_path = "temp_subdir/nested/test.db"
    manager = DatabaseManager(db_path)
    try:
        await manager.init_db()
        assert os.path.exists(os.path.dirname(db_path))
        assert os.path.exists(db_path)
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
        # Clean up directories (optional but good practice)
        if os.path.exists("temp_subdir/nested"):
            os.rmdir("temp_subdir/nested")
        if os.path.exists("temp_subdir"):
            os.rmdir("temp_subdir")
