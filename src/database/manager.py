import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _resolve_storage_dir() -> Path:
    storage_env = os.getenv("FLET_APP_STORAGE_DATA")
    if storage_env:
        path = Path(storage_env) / "ktv-player"
    else:
        path = Path("storage/data")
    path.mkdir(parents=True, exist_ok=True)
    return path


class DatabaseManager:
    """Platform-resilient JSON-backed storage manager matching Colab Shell's StorageService."""

    def __init__(
        self,
        db_path: str = "storage/data/ktv_storage.json",
        storage_path: str | Path | None = None,
    ):
        if storage_path is not None:
            self.storage_dir = Path(storage_path)
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.storage_dir = _resolve_storage_dir()
        self.storage_file = self.storage_dir / "ktv_storage.json"
        self._lock = asyncio.Lock()
        self._data = {
            "settings": {},
            "history": [],
            "favorites": [],
            "playlists": [],
            "custom_channels": [],
            "liveliness_cache": {},
        }
        self._dirty = False

    async def init_db(self) -> None:
        async with self._lock:

            def _load_sync():
                if self.storage_file.exists():
                    try:
                        raw = self.storage_file.read_bytes()
                        if raw:
                            return json.loads(raw.decode("utf-8"))
                    except Exception:
                        bak = self.storage_file.with_suffix(".json.corrupted")
                        with contextlib.suppress(Exception):
                            self.storage_file.replace(bak)
                elif self.storage_file.with_suffix(".json.bak").exists():
                    try:
                        raw = self.storage_file.with_suffix(".json.bak").read_bytes()
                        if raw:
                            return json.loads(raw.decode("utf-8"))
                    except Exception:
                        pass
                return {}

            loaded = await asyncio.to_thread(_load_sync)
            if isinstance(loaded, dict):
                for k in self._data:
                    if k in loaded:
                        self._data[k] = loaded[k]
            logger.info("Database loaded successfully from %s", self.storage_file)

    async def _save_now(self) -> None:
        data_bytes = json.dumps(self._data, ensure_ascii=False, indent=2).encode(
            "utf-8"
        )
        tmp_path = self.storage_file.with_suffix(".json.tmp")
        bak_path = self.storage_file.with_suffix(".json.bak")

        def _write():
            try:
                self.storage_dir.mkdir(parents=True, exist_ok=True)
                if self.storage_file.exists():
                    old = self.storage_file.read_bytes()
                    if old != data_bytes:
                        bak_path.write_bytes(old)
                tmp_path.write_bytes(data_bytes)
                tmp_path.replace(self.storage_file)
            except Exception as e:
                logger.warning("DatabaseManager._save_now failed: %s", e)

        await asyncio.to_thread(_write)
        self._dirty = False

    # --- History ---

    async def save_history(self, url: str):
        async with self._lock:
            history = self._data.setdefault("history", [])
            if url in history:
                history.remove(url)
            history.insert(0, url)
            self._data["history"] = history[:50]
            self._dirty = True
            await self._save_now()

    async def get_history(self, limit: int = 20) -> list[str]:
        async with self._lock:
            return list(self._data.get("history", [])[:limit])

    async def clear_history(self):
        async with self._lock:
            self._data["history"] = []
            self._dirty = True
            await self._save_now()

    # --- Settings ---

    async def set_setting(self, key: str, value: str):
        async with self._lock:
            settings = self._data.setdefault("settings", {})
            settings[key] = str(value)
            self._dirty = True
            await self._save_now()

    async def get_setting(self, key: str, default=None):
        async with self._lock:
            return self._data.get("settings", {}).get(key, default)

    # --- Playlists ---

    async def add_playlist(self, name: str, url: str):
        async with self._lock:
            playlists = self._data.setdefault("playlists", [])
            if not any(p.get("url") == url for p in playlists):
                playlists.append({"name": name, "url": url, "is_active": 1})
                self._dirty = True
                await self._save_now()

    async def get_playlists(self) -> list[dict]:
        async with self._lock:
            return list(self._data.get("playlists", []))

    # --- Custom Channels ---

    async def add_custom_channel(self, name: str, url: str, group: str = "Custom"):
        async with self._lock:
            channels = self._data.setdefault("custom_channels", [])
            if not any(c.get("url") == url for c in channels):
                channels.append({"name": name, "url": url, "logo": "", "group": group})
                self._dirty = True
                await self._save_now()

    async def get_custom_channels(self) -> list[dict]:
        async with self._lock:
            return list(self._data.get("custom_channels", []))

    async def clear_custom_content(self):
        async with self._lock:
            self._data["playlists"] = []
            self._data["custom_channels"] = []
            self._dirty = True
            await self._save_now()

    # --- Favorites ---

    async def add_favorite(self, url: str, name: str = "", logo: str = ""):
        async with self._lock:
            favs = self._data.setdefault("favorites", [])
            favs = [f for f in favs if f.get("url") != url]
            favs.insert(0, {"url": url, "name": name, "logo": logo})
            self._data["favorites"] = favs
            self._dirty = True
            await self._save_now()

    async def remove_favorite(self, url: str):
        async with self._lock:
            favs = self._data.setdefault("favorites", [])
            self._data["favorites"] = [f for f in favs if f.get("url") != url]
            self._dirty = True
            await self._save_now()

    async def get_favorites(self) -> list[dict]:
        async with self._lock:
            return list(self._data.get("favorites", []))

    async def get_favorite_urls(self) -> set[str]:
        async with self._lock:
            return {f["url"] for f in self._data.get("favorites", []) if "url" in f}

    # --- Liveliness Cache ---

    async def save_liveliness_batch(self, entries: list[tuple[str, bool, int]]):
        async with self._lock:
            cache = self._data.setdefault("liveliness_cache", {})
            for url, is_live, updated_at in entries:
                cache[url] = [is_live, updated_at]
            self._dirty = True
            await self._save_now()

    async def load_liveliness_cache(self) -> dict[str, tuple[bool, float]]:
        async with self._lock:
            cache = self._data.get("liveliness_cache", {})
            result = {}
            for url, val in cache.items():
                if isinstance(val, (list, tuple)) and len(val) >= 2:
                    result[url] = (bool(val[0]), float(val[1]))
            return result

    async def clear_liveliness_cache(self):
        async with self._lock:
            self._data["liveliness_cache"] = {}
            self._dirty = True
            await self._save_now()

    async def close(self):
        async with self._lock:
            if self._dirty:
                await self._save_now()


db_manager = DatabaseManager()
