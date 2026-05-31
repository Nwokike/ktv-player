"""Tests for the liveliness cache."""

import time

import pytest

from src.services.liveliness import LivelinessCache


@pytest.fixture
def cache():
    return LivelinessCache(max_size=10, ttl=300)


class TestLivelinessCache:
    def test_get_missing_url(self, cache):
        assert cache.get("http://example.com") is None

    def test_set_and_get(self, cache):
        cache.set("http://example.com", True)
        assert cache.get("http://example.com") is True

    def test_set_and_get_false(self, cache):
        cache.set("http://example.com", False)
        assert cache.get("http://example.com") is False

    def test_ttl_expiry(self):
        short_cache = LivelinessCache(max_size=10, ttl=0)
        short_cache.set("http://example.com", True)
        time.sleep(0.01)
        assert short_cache.get("http://example.com") is None

    def test_max_size_eviction(self):
        small_cache = LivelinessCache(max_size=3, ttl=300)
        for i in range(5):
            small_cache.set(f"http://example.com/{i}", True)
        assert small_cache.get("http://example.com/0") is None
        assert small_cache.get("http://example.com/4") is True

    def test_update_existing_moves_to_end(self):
        small_cache = LivelinessCache(max_size=2, ttl=300)
        small_cache.set("http://first.com", True)
        small_cache.set("http://second.com", True)
        small_cache.set("http://first.com", False)
        small_cache.set("http://third.com", True)
        assert small_cache.get("http://first.com") is False
        assert small_cache.get("http://second.com") is None

    def test_clear(self, cache):
        cache.set("http://example.com", True)
        cache.clear()
        assert cache.get("http://example.com") is None

    def test_drain_dirty(self, cache):
        assert cache.drain_dirty() == []
        cache.set("http://a.com", True)
        cache.set("http://b.com", False)
        dirty = cache.drain_dirty()
        assert len(dirty) == 2
        assert ("http://a.com", True, dirty[0][2]) == dirty[0]
        assert ("http://b.com", False, dirty[1][2]) == dirty[1]
        assert cache.drain_dirty() == []

    def test_load_from_db(self, cache):
        now = time.time()
        entries = {
            "http://a.com": (True, now),
            "http://b.com": (False, now - 10),
        }
        cache.load_from_db(entries)
        assert cache.get("http://a.com") is True
        assert cache.get("http://b.com") is False

    def test_load_from_db_expired_entries(self, cache):
        old = time.time() - 600
        entries = {"http://old.com": (True, old)}
        cache.load_from_db(entries)
        assert cache.get("http://old.com") is None

    def test_load_from_db_respects_max_size(self):
        small_cache = LivelinessCache(max_size=2, ttl=300)
        now = time.time()
        entries = {
            "http://a.com": (True, now),
            "http://b.com": (True, now),
            "http://c.com": (True, now),
        }
        small_cache.load_from_db(entries)
        assert small_cache.get("http://a.com") is True
        assert small_cache.get("http://b.com") is True
        assert small_cache.get("http://c.com") is None

    def test_empty_db_load(self, cache):
        cache.load_from_db({})
        assert cache.get("anything") is None
