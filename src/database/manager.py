import aiosqlite
import os


class DatabaseManager:
    def __init__(self, db_path: str = "storage/data/ktv_player.db"):
        self.db_path = os.path.abspath(db_path)
        self._conn = None

    async def _get_conn(self):
        if self._conn is None:
            db_dir = os.path.dirname(self.db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
            self._conn = await aiosqlite.connect(self.db_path)
            await self._conn.execute("PRAGMA journal_mode=WAL;")
        return self._conn

    async def init_db(self):
        db = await self._get_conn()

        await db.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                name TEXT,
                logo TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                url TEXT UNIQUE,
                is_active INTEGER DEFAULT 1
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS custom_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                url TEXT UNIQUE,
                logo TEXT,
                group_name TEXT DEFAULT 'Custom'
            )
        """)
        await db.commit()

    async def save_history(self, url: str):
        db = await self._get_conn()
        await db.execute("INSERT OR REPLACE INTO history (url) VALUES (?)", (url,))
        await db.commit()

    async def get_history(self):
        db = await self._get_conn()
        async with db.execute(
            "SELECT url FROM history ORDER BY timestamp DESC LIMIT 20"
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def clear_history(self):
        db = await self._get_conn()
        await db.execute("DELETE FROM history")
        await db.commit()

    async def clear_custom_content(self):
        db = await self._get_conn()
        await db.execute("DELETE FROM playlists")
        await db.execute("DELETE FROM custom_channels")
        await db.commit()

    async def set_setting(self, key: str, value: str):
        db = await self._get_conn()
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )
        await db.commit()

    async def get_setting(self, key: str, default=None):
        db = await self._get_conn()
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

    async def add_playlist(self, name: str, url: str):
        db = await self._get_conn()
        await db.execute(
            "INSERT OR IGNORE INTO playlists (name, url) VALUES (?, ?)", (name, url)
        )
        await db.commit()

    async def get_playlists(self):
        db = await self._get_conn()
        async with db.execute("SELECT name, url, is_active FROM playlists") as cursor:
            rows = await cursor.fetchall()
            return [{"name": r[0], "url": r[1], "is_active": r[2]} for r in rows]

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
            "SELECT name, url, logo, group_name FROM custom_channels"
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"name": r[0], "url": r[1], "logo": r[2], "group": r[3]} for r in rows]

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


db_manager = DatabaseManager()
