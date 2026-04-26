import pytest
import os
import aiosqlite
from database.manager import DatabaseManager

@pytest.fixture
async def db_manager():
    db_path = "test_ktv_ext.db"
    manager = DatabaseManager(db_path)
    await manager.init_db()
    yield manager
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.mark.asyncio
async def test_favorites_management(db_manager):
    # This assumes we add a save_favorite method
    # For now we'll just test the table exists by inserting manually
    async with aiosqlite.connect(db_manager.db_path) as db:
        await db.execute("INSERT INTO favorites (url, name) VALUES (?, ?)", ("url1", "Channel 1"))
        await db.commit()
        
        async with db.execute("SELECT name FROM favorites WHERE url=?", ("url1",)) as cursor:
            row = await cursor.fetchone()
            assert row[0] == "Channel 1"

@pytest.mark.asyncio
async def test_settings_persistence(db_manager):
    async with aiosqlite.connect(db_manager.db_path) as db:
        await db.execute("INSERT INTO settings (key, value) VALUES (?, ?)", ("theme", "dark"))
        await db.commit()
        
        async with db.execute("SELECT value FROM settings WHERE key=?", ("theme",)) as cursor:
            row = await cursor.fetchone()
            assert row[0] == "dark"
