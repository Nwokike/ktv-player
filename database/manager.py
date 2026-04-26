import aiosqlite
import os

class DatabaseManager:
    def __init__(self, db_path: str = "ktv_player.db"):
        self.db_path = db_path

    async def init_db(self):
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

# Shared instance
db_manager = DatabaseManager()
