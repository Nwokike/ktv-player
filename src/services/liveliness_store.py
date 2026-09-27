"""Liveliness verdict persistence: cache-class, not durable state.

Probe results are re-derivable (a dead dot re-probes within minutes), so
per the storage contract (FLET_APP_STORAGE_CACHE) they belong in the
cache directory, not in the durable JSON database. The old DB-backed
store had two problems this replaces:

- it rewrote the ENTIRE durable database (favorites, history, settings,
  license) after every probe batch, churning flash storage for data the
  OS is allowed to purge anyway;
- it kept cache-class bytes alive across updates they have no business
  surviving.

Migration is one-shot and silent: an existing DB cache is imported on
first load, written to the cache dir, then cleared from the database.
"""

import asyncio
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

_cache_env = os.getenv("FLET_APP_STORAGE_CACHE")
STORE_PATH = (
    os.path.join(_cache_env, "liveliness.json")
    if _cache_env
    else os.path.join("storage", "liveliness.json")
)
# A verdict older than this is re-probed on demand anyway; pruning bounds
# the file and honors the cache contract (the OS may wipe this file too).
PRUNE_AFTER_SECONDS = 30 * 24 * 60 * 60

_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


def _read() -> dict | None:
    try:
        if os.path.exists(STORE_PATH):
            with open(STORE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        logger.debug("Liveliness store unreadable, treating as empty", exc_info=True)
    return None


def _write(data: dict) -> None:
    """Atomic: temp file beside the target, then rename (same filesystem,
    so os.replace cannot fail across devices like it would from temp/)."""
    directory = os.path.dirname(STORE_PATH) or "."
    os.makedirs(directory, exist_ok=True)
    tmp_path = STORE_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp_path, STORE_PATH)


async def load_cache() -> dict:
    """Verdicts from the cache dir, importing a legacy DB copy once."""
    data = _read()
    if data is not None:
        return data
    try:
        # Lazy import: main and the checker import this module long before
        # the database manager is initialized.
        from database.manager import db_manager

        legacy = await db_manager.load_liveliness_cache()
        if legacy:
            data = {url: list(entry) for url, entry in legacy.items()}
            _write(data)
            await db_manager.clear_liveliness_cache()
            logger.info(
                "Migrated %d liveliness verdicts from the database to the cache dir",
                len(data),
            )
            return data
    except Exception:
        logger.debug("Liveliness migration failed", exc_info=True)
    return {}


async def save_batch(entries: list) -> None:
    """Merge dirty verdicts into the cache file (serialized, atomic,
    pruning entries too old to matter)."""
    async with _get_lock():
        data = _read() or {}
        now = time.time()
        for url, is_live, updated_at in entries:
            data[url] = [bool(is_live), float(updated_at)]
        if data:
            data = {
                url: entry
                for url, entry in data.items()
                if now - float(entry[1]) < PRUNE_AFTER_SECONDS
            }
        await asyncio.to_thread(_write, data)
