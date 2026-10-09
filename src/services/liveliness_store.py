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

Format: msgpack with a schema version stamp (Phase 8; msgpack is a
direct dependency — previously transitive-only via flet, so an upgrade
could have pruned it). A legacy JSON file is imported once on first
msgpack load; a corrupt msgpack payload falls back to empty (verdicts
are re-derivable, nothing is lost that matters). Migration from the
durable DB is one-shot and silent, as before.
"""

import asyncio
import contextlib
import json
import logging
import os
import time

import anyio
import msgpack

logger = logging.getLogger(__name__)

_cache_env = os.getenv("FLET_APP_STORAGE_CACHE")
STORE_PATH = (
    os.path.join(_cache_env, "liveliness.mpk")
    if _cache_env
    else os.path.join("storage", "liveliness.mpk")
)
_LEGACY_JSON_PATH = (
    os.path.join(_cache_env, "liveliness.json")
    if _cache_env
    else os.path.join("storage", "liveliness.json")
)
# A verdict older than this is re-probed on demand anyway; pruning bounds
# the file and honors the cache contract (the OS may wipe this file too).
PRUNE_AFTER_SECONDS = 30 * 24 * 60 * 60

# Schema stamp: bump when the entry shape changes; mismatches are treated
# as empty rather than misread.
_SCHEMA_VERSION = 1

_lock: asyncio.Lock | None = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


def _decode_payload(raw: bytes) -> dict | None:
    """Unpack a schema-stamped msgpack payload; None when unusable."""
    try:
        decoded = msgpack.unpackb(raw, raw=False, strict_map_key=False)
    except (ValueError, TypeError, msgpack.UnpackException):
        return None
    if not isinstance(decoded, dict):
        return None
    if decoded.get("v") != _SCHEMA_VERSION:
        return None
    entries = decoded.get("entries")
    return entries if isinstance(entries, dict) else None


def _read() -> dict | None:
    try:
        if os.path.exists(STORE_PATH):
            with open(STORE_PATH, "rb") as f:
                raw = f.read()
            data = _decode_payload(raw)
            if data is not None:
                return data
            logger.debug("Liveliness store unreadable, treating as empty")
            return None
        # One-shot legacy JSON import (pre-msgpack file).
        if os.path.exists(_LEGACY_JSON_PATH):
            with open(_LEGACY_JSON_PATH, encoding="utf-8") as f:
                legacy = json.load(f)
            os.remove(_LEGACY_JSON_PATH)
            return legacy if isinstance(legacy, dict) else None
    except (OSError, ValueError, TypeError, msgpack.UnpackException):
        logger.debug("Liveliness store unreadable, treating as empty", exc_info=True)
    return None


def _encode_payload(data: dict) -> bytes:
    return msgpack.packb({"v": _SCHEMA_VERSION, "entries": data}, use_bin_type=True)


def _write(data: dict) -> None:
    """Atomic: temp file beside the target, then rename (same filesystem,
    so os.replace cannot fail across devices like it would from temp/).

    fsync before the replace so a power loss mid-write cannot leave a
    half-flushed .mpk (rename after write only orders the metadata, not
    the data, on some filesystems). Tmp is unlinked on any failure.
    """
    directory = os.path.dirname(STORE_PATH) or "."
    os.makedirs(directory, exist_ok=True)
    tmp_path = STORE_PATH + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(_encode_payload(data))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, STORE_PATH)
    except OSError:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


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
        await anyio.to_thread.run_sync(_write, data)
