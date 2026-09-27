"""Liveliness verdicts are cache-class: own file, migrated once, pruned.

Probe results used to live in the durable JSON database, which meant the
ENTIRE database (favorites, history, settings, license) was rewritten
after every probe batch for data the OS is allowed to purge anyway.
"""

import asyncio
import time
from unittest import mock

import pytest

from services import liveliness_store


@pytest.mark.asyncio
async def test_roundtrip_through_the_cache_file(tmp_path, monkeypatch):
    store = tmp_path / "liveliness.json"
    monkeypatch.setattr(liveliness_store, "STORE_PATH", str(store))

    now = time.time()
    await liveliness_store.save_batch([("http://a", True, now)])

    assert store.exists(), "verdicts belong in the cache dir"
    assert not (tmp_path / "liveliness.json.tmp").exists(), "temp must be renamed away"
    data = await liveliness_store.load_cache()
    assert data == {"http://a": [True, now]}


@pytest.mark.asyncio
async def test_legacy_database_copy_is_migrated_exactly_once(tmp_path, monkeypatch):
    store = tmp_path / "liveliness.json"
    monkeypatch.setattr(liveliness_store, "STORE_PATH", str(store))

    now = time.time()
    db = mock.Mock()

    async def load():
        return {"http://legacy": [False, now]}

    async def clear():
        db.cleared = True

    db.load_liveliness_cache.side_effect = load
    db.clear_liveliness_cache.side_effect = clear

    with mock.patch("database.manager.db_manager", db):
        data = await liveliness_store.load_cache()
        assert data == {"http://legacy": [False, now]}
        assert db.cleared, "the durable database must shed its cache-class copy"
        assert store.exists()

        # File exists now: the database must never be touched again.
        db.load_liveliness_cache.side_effect = AssertionError(
            "load must not reach the database once the cache file exists"
        )
        second = await liveliness_store.load_cache()
    assert "http://legacy" in second


@pytest.mark.asyncio
async def test_stale_verdicts_are_pruned_on_save(tmp_path, monkeypatch):
    store = tmp_path / "liveliness.json"
    monkeypatch.setattr(liveliness_store, "STORE_PATH", str(store))

    ancient = time.time() - 40 * 24 * 3600
    await liveliness_store.save_batch(
        [("http://old", True, ancient), ("http://new", True, time.time())]
    )

    data = await liveliness_store.load_cache()
    assert list(data) == ["http://new"], "30-day-old verdicts must not accumulate"


@pytest.mark.asyncio
async def test_concurrent_batches_do_not_lose_entries(tmp_path, monkeypatch):
    store = tmp_path / "liveliness.json"
    monkeypatch.setattr(liveliness_store, "STORE_PATH", str(store))

    now = time.time()
    await liveliness_store.save_batch([("http://seed", True, now)])
    # Two probe workers persisting at once: the lock serializes the
    # read-modify-write so neither entry is lost.
    await asyncio.gather(
        liveliness_store.save_batch([("http://w1", True, now)]),
        liveliness_store.save_batch([("http://w2", False, now)]),
    )

    data = await liveliness_store.load_cache()
    assert {"http://seed", "http://w1", "http://w2"} <= set(data)
