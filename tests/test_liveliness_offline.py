"""Offline liveliness: no probes while offline, dots stay neutral, checks
resume when connectivity returns."""

import pytest

# Import via the app path (not src.*) so these tests share the exact module
# instances (and singletons) the application code uses.
from services import liveliness_checker as lc
from services.liveliness import liveliness_cache


@pytest.fixture(autouse=True)
def _clean_state():
    lc.state.reset()
    liveliness_cache.clear()
    lc.drain_queue()
    yield
    lc.state.reset()
    liveliness_cache.clear()
    lc.drain_queue()


def test_enqueue_skipped_while_offline():
    lc.state.is_online = False
    queue_before = lc._liveliness_queue
    lc.enqueue_liveliness_check("http://offline.example/a")
    assert lc._liveliness_queue is queue_before  # queue not even created
    assert "http://offline.example/a" not in lc._in_flight


@pytest.mark.asyncio
async def test_enqueue_works_when_online():
    lc.state.is_online = True
    lc.enqueue_liveliness_check("http://online.example/a")
    assert "http://online.example/a" in lc._in_flight
    lc.shutdown_workers()
    lc.drain_queue()


@pytest.mark.asyncio
async def test_check_single_offline_returns_without_caching():
    """An offline probe must not write False into the cache — the dot stays
    neutral (None) instead of turning red."""
    lc.state.is_online = False
    checker = lc.LivelinessChecker(None)
    result = await checker.check_single("http://offline.example/b")
    assert result == ("http://offline.example/b", False)
    assert liveliness_cache.get("http://offline.example/b") is None
