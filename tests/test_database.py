import pytest
import os
import aiosqlite
from database.manager import DatabaseManager

@pytest.fixture
async def db_manager():
    db_path = "test_ktv.db"
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
async def test_wal_mode(db_manager):
    async with aiosqlite.connect(db_manager.db_path) as db:
        async with db.execute("PRAGMA journal_mode") as cursor:
            row = await cursor.fetchone()
            assert row[0].upper() == "WAL"
