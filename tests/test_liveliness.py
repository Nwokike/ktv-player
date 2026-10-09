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
        # ttl=0 expires on the next read already — no real sleep needed.
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


class TestMultiSubscriber:
    """Phase 3: Home + Search + Grid listen without clobbering each other."""

    def test_two_subscribers_both_fire(self, cache):
        seen = []
        cache.add_on_change(lambda url: seen.append(("a", url)))
        cache.add_on_change(lambda url: seen.append(("b", url)))
        cache.set("http://x", True)
        assert ("a", "http://x") in seen
        assert ("b", "http://x") in seen

    def test_remove_stops_one_subscriber(self, cache):
        seen = []
        unsub = cache.add_on_change(lambda url: seen.append(("a", url)))
        cache.add_on_change(lambda url: seen.append(("b", url)))
        unsub()
        cache.set("http://x", True)
        assert ("a", "http://x") not in seen
        assert ("b", "http://x") in seen

    def test_set_on_change_shim_is_gone(self, cache):
        """The single-slot shim was deleted with the per-card subscription
        migration (Phase 8) — it would clobber card subscriptions."""
        assert not hasattr(cache, "set_on_change")

    def test_clear_notifies_subscribers(self, cache):
        seen = []
        cache.add_on_change(lambda url: seen.append(url))
        cache.set("http://x", True)
        cache.clear()
        assert None in seen

    def test_subscriber_exception_does_not_break_others(self, cache):
        seen = []

        def _boom(url):
            raise RuntimeError("subscriber bug")

        cache.add_on_change(_boom)
        cache.add_on_change(lambda url: seen.append(url))
        cache.set("http://x", True)  # must not raise
        assert seen == ["http://x"]


class TestTriStateUnknown:
    """Phase 4: local/pool/offline failures are UNKNOWN (no cache, no red)."""

    @pytest.mark.asyncio
    async def test_pool_timeout_is_unknown(self):
        from unittest import mock

        import httpx

        import services.liveliness_checker as lc
        from services.liveliness import liveliness_cache

        checker = lc.LivelinessChecker(None)
        http_client = mock.MagicMock()
        http_client.head = mock.AsyncMock(
            side_effect=httpx.PoolTimeout("pool exhausted")
        )
        http_client.get = mock.AsyncMock(
            side_effect=httpx.PoolTimeout("pool exhausted")
        )
        old_online = lc.state.is_online
        lc.state.is_online = True
        try:
            with mock.patch.object(
                checker, "_get_http_client", return_value=http_client
            ):
                url = "http://tristate-pool.example/s.m3u8"
                result = await checker.check_single(url)
                assert result == (url, None)
                assert liveliness_cache.get(url) is None
        finally:
            lc.state.is_online = old_online

    def test_semaphore_is_shared_module_level(self):
        import asyncio

        import services.liveliness_checker as lc

        assert isinstance(lc._PROBE_SEMAPHORE, asyncio.Semaphore)
        a = lc.LivelinessChecker(None)
        b = lc.LivelinessChecker(None)
        assert not hasattr(a, "_semaphore")
        assert not hasattr(b, "_semaphore")

    def test_live_predicate_unified(self):
        from services.liveliness_checker import _is_live_status

        for good in (200, 201, 204, 206, 299, 301, 399):
            assert _is_live_status(good) is True
        for bad in (0, 199, 400, 404, 405, 500):
            assert _is_live_status(bad) is False
