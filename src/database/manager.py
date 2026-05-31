import asyncio
import logging
import os
import shutil

import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path: str = "storage/data/ktv_player.db"):
        self.db_path = os.path.abspath(db_path)
        self._conn = None
        self._conn_lock = asyncio.Lock()

    async def _get_conn(self):
        async with self._conn_lock:
            if self._conn is not None:
                return self._conn
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self._conn = await aiosqlite.connect(self.db_path)
            await self._conn.execute("PRAGMA journal_mode=WAL;")
            await self._conn.execute("PRAGMA synchronous=NORMAL;")
            await self._conn.execute("PRAGMA cache_size=-4000;")

            # Check for corruption and recover properly
            try:
                cursor = await self._conn.execute("PRAGMA quick_check;")
                result = await cursor.fetchone()
                if result and result[0] != "ok":
                    logger.warning("Database corruption detected, recovering...")
                    await self._conn.close()
                    self._conn = None
                    # Back up corrupted file, then delete it so we start fresh
                    backup = self.db_path + ".corrupted"
                    if os.path.exists(self.db_path):
                        shutil.copy2(self.db_path, backup)
                        os.remove(self.db_path)
                        logger.info(
                            "Corrupted DB backed up to %s, creating fresh DB",
                            backup,
                        )
                    self._conn = await aiosqlite.connect(self.db_path)
                    await self._conn.execute("PRAGMA journal_mode=WAL;")
                    await self._conn.execute("PRAGMA synchronous=NORMAL;")
                    await self._conn.execute("PRAGMA cache_size=-4000;")
            except Exception:
                pass
            await self._init_tables()
        return self._conn

    async def _init_tables(self):
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                name TEXT,
                logo TEXT
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                url TEXT UNIQUE,
                is_active INTEGER DEFAULT 1
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS liveliness_cache (
                url TEXT PRIMARY KEY,
                is_live INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS custom_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                url TEXT UNIQUE,
                logo TEXT,
                group_name TEXT DEFAULT 'Custom'
            )
        """)
        await self._conn.commit()

    async def init_db(self):
        await self._get_conn()

    # --- History ---

    async def save_history(self, url: str):
        db = await self._get_conn()
        await db.execute("INSERT OR REPLACE INTO history (url) VALUES (?)", (url,))
        await db.commit()

    async def get_history(self, limit: int = 20):
        db = await self._get_conn()
        async with db.execute(
            "SELECT url FROM history ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def clear_history(self):
        db = await self._get_conn()
        await db.execute("DELETE FROM history")
        await db.commit()

    # --- Settings ---

    async def set_setting(self, key: str, value: str):
        db = await self._get_conn()
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await db.commit()

    async def get_setting(self, key: str, default=None):
        db = await self._get_conn()
        async with db.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

    # --- Playlists ---

    async def add_playlist(self, name: str, url: str):
        db = await self._get_conn()
        await db.execute(
            "INSERT OR IGNORE INTO playlists (name, url) VALUES (?, ?)",
            (name, url),
        )
        await db.commit()

    async def get_playlists(self):
        db = await self._get_conn()
        async with db.execute("SELECT name, url, is_active FROM playlists") as cursor:
            rows = await cursor.fetchall()
            return [{"name": r[0], "url": r[1], "is_active": r[2]} for r in rows]

    # --- Custom Channels ---

    async def add_custom_channel(self, name: str, url: str, group: str = "Custom"):
        db = await self._get_conn()
        await db.execute(
            "INSERT OR IGNORE INTO custom_channels (name, url, group_name) VALUES (?, ?, ?)",
            (name, url, group),
        )
        await db.commit()

    async def get_custom_channels(self):
        db = await self._get_conn()
        async with db.execute(
            "SELECT name, url, logo, group_name FROM custom_channels",
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                {"name": r[0], "url": r[1], "logo": r[2], "group": r[3]} for r in rows
            ]

    async def clear_custom_content(self):
        db = await self._get_conn()
        await db.execute("DELETE FROM playlists")
        await db.execute("DELETE FROM custom_channels")
        await db.commit()

    # --- Favorites ---

    async def add_favorite(self, url: str, name: str = "", logo: str = ""):
        db = await self._get_conn()
        await db.execute(
            "INSERT OR REPLACE INTO favorites (url, name, logo) VALUES (?, ?, ?)",
            (url, name, logo),
        )
        await db.commit()

    async def remove_favorite(self, url: str):
        db = await self._get_conn()
        await db.execute("DELETE FROM favorites WHERE url = ?", (url,))
        await db.commit()

    async def get_favorites(self):
        db = await self._get_conn()
        async with db.execute(
            "SELECT url, name, logo FROM favorites ORDER BY id DESC",
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"url": r[0], "name": r[1], "logo": r[2]} for r in rows]

    async def get_favorite_urls(self) -> set[str]:
        db = await self._get_conn()
        async with db.execute("SELECT url FROM favorites") as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

    # --- Liveliness Cache ---

    async def save_liveliness_batch(self, entries: list[tuple[str, bool, int]]):
        db = await self._get_conn()
        await db.executemany(
            "INSERT OR REPLACE INTO liveliness_cache (url, is_live, updated_at) VALUES (?, ?, ?)",
            entries,
        )
        await db.commit()

    async def load_liveliness_cache(self) -> dict[str, tuple[bool, float]]:
        db = await self._get_conn()
        async with db.execute(
            "SELECT url, is_live, updated_at FROM liveliness_cache",
        ) as cursor:
            rows = await cursor.fetchall()
            return {r[0]: (bool(r[1]), float(r[2])) for r in rows}

    async def clear_liveliness_cache(self):
        db = await self._get_conn()
        await db.execute("DELETE FROM liveliness_cache")
        await db.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


db_manager = DatabaseManager()
