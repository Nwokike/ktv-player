import aiosqlite
import os

class DatabaseManager:
    def __init__(self, db_path: str = "storage/data/ktv_player.db"):
        # Convert to an absolute path so Codespaces/Docker always knows exactly where it is
        self.db_path = os.path.abspath(db_path)

    async def init_db(self):
        # CRITICAL FIX: Force create the directory folders if they do not exist
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for performance
            await db.execute("PRAGMA journal_mode=WAL;")
            
            # History table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Favorites table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    name TEXT,
                    logo TEXT
                )
            """)
            
            # Settings table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            
            # Playlists table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    url TEXT UNIQUE,
                    is_active INTEGER DEFAULT 1
                )
            """)
            
            # Individual Custom Channels
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
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO history (url) VALUES (?)", (url,))
            await db.commit()

    async def get_history(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT url FROM history ORDER BY timestamp DESC LIMIT 20") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def set_setting(self, key: str, value: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
            await db.commit()

    async def get_setting(self, key: str, default=None):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else default

    async def add_playlist(self, name: str, url: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO playlists (name, url) VALUES (?, ?)", (name, url))
            await db.commit()

    async def get_playlists(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT name, url, is_active FROM playlists") as cursor:
                rows = await cursor.fetchall()
                return [{"name": r[0], "url": r[1], "is_active": r[2]} for r in rows]

    async def add_custom_channel(self, name: str, url: str, group: str = "Custom"):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT OR IGNORE INTO custom_channels (name, url, group_name) VALUES (?, ?, ?)", (name, url, group))
            await db.commit()

    async def get_custom_channels(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT name, url, logo, group_name FROM custom_channels") as cursor:
                rows = await cursor.fetchall()
                return [{"name": r[0], "url": r[1], "logo": r[2], "group": r[3]} for r in rows]

# Shared instance
db_manager = DatabaseManager()
