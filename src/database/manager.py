import asyncio
import contextlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import anyio

logger = logging.getLogger(__name__)

# Schema version for the durable JSON store. Bumped when the shape of _data
# changes incompatibly; init_db can migrate older versions here.
SCHEMA_VERSION = 1


def _resolve_storage_dir() -> Path:
    storage_env = os.getenv("FLET_APP_STORAGE_DATA")
    path = Path(storage_env) / "ktv-player" if storage_env else Path("storage/data")
    return path


def _ensure_storage_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _coerce_entry_dict(e: Any, url_key: str = "url") -> dict | None:
    """Normalize one stored row to a dict with a usable URL, or None to drop."""
    if isinstance(e, str):
        e = {"url": e, "title": e}
    if not isinstance(e, dict):
        return None
    url = e.get(url_key)
    if not isinstance(url, str) or not url.strip():
        return None
    return e


class DatabaseManager:
    """JSON-backed storage manager with atomic writes and corruption recovery."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        storage_path: str | Path | None = None,
    ):
        if storage_path is not None:
            self.storage_dir = Path(storage_path)
        elif db_path is not None:
            # db_path names the storage FILE (historical quirk: the default
            # looked like a file path). Honor it: parent dir + file name.
            p = Path(db_path)
            self.storage_dir = p.parent
            self._explicit_file = p.name
        else:
            self.storage_dir = _resolve_storage_dir()
            self._explicit_file = "ktv_storage.json"
        if not hasattr(self, "_explicit_file"):
            self._explicit_file = "ktv_storage.json"
        self.storage_file = self.storage_dir / self._explicit_file
        # No I/O in __init__: directory creation happens lazily on first
        # write so importing the module (or constructing in tests) never
        # creates directories as a side effect.
        self._lock = asyncio.Lock()
        self._data = {
            "schema_version": SCHEMA_VERSION,
            "settings": {},
            "history": [],
            "favorites": [],
            "playlists": [],
            "custom_channels": [],
            "liveliness_cache": {},
        }
        self._dirty = False

    def _validate_loaded(self, loaded: dict) -> tuple[dict, bool]:
        """Coerce a parsed store into shape; returns (data, dirty).

        Legacy rows (plain strings, ints, dicts with missing/blank URLs) are
        migrated or dropped with a log line instead of crashing every reader.
        Unknown top-level keys are preserved (forward compatibility); missing
        known keys fall back to defaults.
        """
        data = dict(self._data)
        dirty = False
        for key in ("history", "favorites", "playlists", "custom_channels"):
            raw = loaded.get(key, [])
            if not isinstance(raw, list):
                logger.warning("DB key %r is not a list; resetting", key)
                data[key] = []
                dirty = True
                continue
            clean: list[dict] = []
            dropped = 0
            for e in raw:
                if key == "history" and isinstance(e, str):
                    e = {"url": e, "title": e}
                    dirty = True
                row = _coerce_entry_dict(e)
                if row is None:
                    dropped += 1
                    dirty = True
                    continue
                clean.append(row if row is e else dict(row))
            if dropped:
                logger.warning("DB key %r: dropped %d invalid rows", key, dropped)
            data[key] = clean
        settings = loaded.get("settings", {})
        data["settings"] = dict(settings) if isinstance(settings, dict) else {}
        if not isinstance(settings, dict):
            dirty = True
        cache = loaded.get("liveliness_cache", {})
        data["liveliness_cache"] = dict(cache) if isinstance(cache, dict) else {}
        # Preserve unknown keys verbatim.
        for k, v in loaded.items():
            if k not in data:
                data[k] = v
        return data, dirty

    async def init_db(self) -> None:
        async with self._lock:

            def _load_sync():
                bak_path = self.storage_file.with_suffix(".json.bak")

                def _try_read(path: Path):
                    try:
                        raw = path.read_bytes()
                    except OSError:
                        return None
                    if not raw:
                        # Empty file is NOT a clean empty DB: it usually means
                        # a crashed write. Signal fallback, don't accept it.
                        return None
                    try:
                        return json.loads(raw.decode("utf-8"))
                    except Exception:
                        return None

                main = (
                    _try_read(self.storage_file) if self.storage_file.exists() else None
                )
                if isinstance(main, dict):
                    return main, False
                if self.storage_file.exists():
                    # Main exists but is corrupt/empty: quarantine with a
                    # timestamp (never overwrite previous forensics), then
                    # fall THROUGH to the backup instead of returning {}.
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    quarantine = self.storage_file.with_suffix(f".corrupted.{ts}")
                    try:
                        self.storage_file.replace(quarantine)
                        logger.warning(
                            "Main DB corrupt/empty; quarantined to %s", quarantine
                        )
                    except OSError:
                        logger.exception("Failed to quarantine corrupt DB")
                backup = _try_read(bak_path) if bak_path.exists() else None
                if isinstance(backup, dict):
                    logger.warning("Recovered DB from backup %s", bak_path)
                    return backup, False
                return {}, False

            loaded, _ = await anyio.to_thread.run_sync(_load_sync)
            if isinstance(loaded, dict):
                data, dirty = self._validate_loaded(loaded)
                self._data = data
                self._dirty = dirty
            logger.info("Database loaded successfully from %s", self.storage_file)
            if self._dirty:
                # Persist migrations immediately so the next boot is clean.
                await self._save_now_locked()

    async def _save_now_locked(self) -> bool:
        """Write _data atomically. Caller must hold _lock. Returns success."""
        try:
            data_bytes = json.dumps(self._data, ensure_ascii=False, indent=2).encode(
                "utf-8"
            )
        except (TypeError, ValueError):
            logger.exception("DatabaseManager: data not serializable; not saving")
            return False
        tmp_path = self.storage_dir / (self.storage_file.name + ".tmp")
        bak_path = self.storage_file.with_suffix(".json.bak")

        def _write() -> bool:
            try:
                _ensure_storage_dir(self.storage_dir)
                if self.storage_file.exists():
                    old = self.storage_file.read_bytes()
                    if old != data_bytes:
                        bak_path.write_bytes(old)
                tmp_path.write_bytes(data_bytes)
                with (
                    open(tmp_path, "rb") as f,
                    contextlib.suppress(OSError),
                ):
                    os.fsync(f.fileno())
                tmp_path.replace(self.storage_file)
                return True
            except Exception as e:
                logger.warning("DatabaseManager._save_now failed: %s", e)
                with contextlib.suppress(OSError):
                    tmp_path.unlink(missing_ok=True)
                return False

        ok = await anyio.to_thread.run_sync(_write)
        if ok:
            self._dirty = False
        return ok

    async def _save_now(self) -> bool:
        # Lock-free entry point for close() (which already holds _lock) is
        # _save_now_locked; this wrapper takes the lock for regular callers.
        async with self._lock:
            return await self._save_now_locked()

    # --- History ---

    async def save_history(self, url: str, title: str = "") -> bool:
        async with self._lock:
            history = self._data.setdefault("history", [])
            # Preserve any existing position so re-plays don't reset progress
            existing = next(
                (e for e in history if isinstance(e, dict) and e.get("url") == url),
                None,
            )
            carried_position = (
                existing.get("position") if isinstance(existing, dict) else None
            )
            carried_duration = (
                existing.get("duration") if isinstance(existing, dict) else None
            )
            # Remove existing entry with same URL
            history = [
                e for e in history if not (isinstance(e, dict) and e.get("url") == url)
            ]
            entry: dict = {"url": url, "title": title or url}
            if carried_position is not None:
                entry["position"] = carried_position
            if carried_duration is not None:
                entry["duration"] = carried_duration
            history.insert(0, entry)
            self._data["history"] = history[:50]
            self._dirty = True
            return await self._save_now_locked()

    async def update_history_position(
        self, url: str, position: float, duration: float | None = None
    ) -> bool:
        """Update the saved playback position for a history entry.

        No-op (returns False) if no history entry exists for `url`.
        """
        async with self._lock:
            for e in self._data.setdefault("history", []):
                if isinstance(e, dict) and e.get("url") == url:
                    e["position"] = max(0.0, float(position))
                    if duration is not None:
                        e["duration"] = max(0.0, float(duration))
                    self._dirty = True
                    await self._save_now_locked()
                    return True
            return False

    async def get_history_entry(self, url: str) -> dict | None:
        async with self._lock:
            for e in self._data.get("history", []):
                if isinstance(e, dict) and e.get("url") == url:
                    return dict(e)
            return None

    def get_history_entry_sync(self, url: str) -> dict | None:
        """Sync accessor for use from synchronous contexts (e.g. component
        __init__). Safe because the underlying data is only mutated under
        `_lock` and we return a shallow copy of the entry dict.
        """
        for e in self._data.get("history", []):
            if isinstance(e, dict) and e.get("url") == url:
                return dict(e)
        return None

    async def get_history(self, limit: int = 20) -> list[dict]:
        async with self._lock:
            raw = self._data.get("history", [])[:limit]
            # Defensive copy: callers must not mutate internal rows.
            # (Persistent legacy strings are migrated once in init_db.)
            return [dict(e) for e in raw if isinstance(e, dict)]

    async def clear_history(self) -> bool:
        async with self._lock:
            self._data["history"] = []
            self._dirty = True
            return await self._save_now_locked()

    # --- Settings ---

    async def set_setting(self, key: str, value: Any) -> bool:
        async with self._lock:
            settings = self._data.setdefault("settings", {})
            settings[key] = value
            self._dirty = True
            return await self._save_now_locked()

    async def delete_setting(self, key: str) -> bool:
        async with self._lock:
            settings = self._data.setdefault("settings", {})
            if key not in settings:
                return False
            del settings[key]
            self._dirty = True
            return await self._save_now_locked()

    async def get_setting(self, key: str, default: Any = None) -> Any:
        async with self._lock:
            return self._data.get("settings", {}).get(key, default)

    # --- Playlists ---

    async def add_playlist(self, name: str, url: str) -> bool:
        """Returns True when added, False when the URL already exists."""
        async with self._lock:
            playlists = self._data.setdefault("playlists", [])
            if not any(isinstance(p, dict) and p.get("url") == url for p in playlists):
                playlists.append({"name": name, "url": url, "is_active": 1})
                self._dirty = True
                await self._save_now_locked()
                return True
            return False

    async def get_playlists(self) -> list[dict]:
        async with self._lock:
            return [
                dict(p) for p in self._data.get("playlists", []) if isinstance(p, dict)
            ]

    # --- Custom Channels ---

    async def add_custom_channel(
        self, name: str, url: str, group: str = "Custom"
    ) -> bool:
        """Returns True when added, False when the URL already exists."""
        async with self._lock:
            channels = self._data.setdefault("custom_channels", [])
            if not any(isinstance(c, dict) and c.get("url") == url for c in channels):
                channels.append({"name": name, "url": url, "logo": "", "group": group})
                self._dirty = True
                await self._save_now_locked()
                return True
            return False

    async def get_custom_channels(self) -> list[dict]:
        async with self._lock:
            return [
                dict(c)
                for c in self._data.get("custom_channels", [])
                if isinstance(c, dict)
            ]

    async def clear_custom_content(self) -> bool:
        async with self._lock:
            self._data["playlists"] = []
            self._data["custom_channels"] = []
            self._dirty = True
            return await self._save_now_locked()

    # --- Favorites ---

    async def add_favorite(self, url: str, name: str = "", logo: str = "") -> bool:
        async with self._lock:
            favs = self._data.setdefault("favorites", [])
            favs = [
                f for f in favs if not (isinstance(f, dict) and f.get("url") == url)
            ]
            favs.insert(0, {"url": url, "name": name, "logo": logo})
            self._data["favorites"] = favs
            self._dirty = True
            await self._save_now_locked()
            return True

    async def remove_favorite(self, url: str) -> bool:
        async with self._lock:
            favs = self._data.setdefault("favorites", [])
            kept = [
                f for f in favs if not (isinstance(f, dict) and f.get("url") == url)
            ]
            if len(kept) == len(favs):
                return False
            self._data["favorites"] = kept
            self._dirty = True
            await self._save_now_locked()
            return True

    async def get_favorites(self) -> list[dict]:
        async with self._lock:
            return [
                dict(f) for f in self._data.get("favorites", []) if isinstance(f, dict)
            ]

    async def remap_favorite_url(self, old_url: str, new_url: str) -> bool:
        """Re-key one favorite onto a new stream URL (playlist swap).

        Favorites are URL-keyed, so when the source changes underneath
        them the star silently disappears from the grid. Returns True
        when the entry moved; unmatched favorites are never deleted.
        A pre-existing entry under new_url is merged (dropped) instead of
        duplicated.
        """
        async with self._lock:
            favs = self._data.setdefault("favorites", [])
            target = None
            for fav in favs:
                if isinstance(fav, dict) and fav.get("url") == old_url:
                    target = fav
                    break
            if target is None:
                return False
            if any(
                f is not target and isinstance(f, dict) and f.get("url") == new_url
                for f in favs
            ):
                favs.remove(target)
            else:
                target["url"] = new_url
            self._dirty = True
            await self._save_now_locked()
            return True

    async def get_favorite_urls(self) -> set[str]:
        async with self._lock:
            return {
                f["url"]
                for f in self._data.get("favorites", [])
                if isinstance(f, dict) and isinstance(f.get("url"), str)
            }

    # --- Liveliness Cache ---
    # Probes moved to services/liveliness_store.py (cache-class data).
    # load/clear remain here: the store imports the legacy copy once on
    # migration and then removes it from the durable database.

    async def load_liveliness_cache(self) -> dict[str, tuple[bool, float]]:
        async with self._lock:
            cache = self._data.get("liveliness_cache", {})
            result = {}
            for url, val in cache.items():
                try:
                    if isinstance(val, (list, tuple)) and len(val) >= 2:
                        result[url] = (bool(val[0]), float(val[1]))
                except (TypeError, ValueError):
                    continue
            return result

    async def clear_liveliness_cache(self) -> bool:
        async with self._lock:
            self._data["liveliness_cache"] = {}
            self._dirty = True
            return await self._save_now_locked()

    async def close(self) -> None:
        async with self._lock:
            if self._dirty:
                await self._save_now_locked()


db_manager = DatabaseManager()
