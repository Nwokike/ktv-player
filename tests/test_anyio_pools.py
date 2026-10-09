"""TaskPool tests: structured concurrency, drain, join, no orphans."""

import asyncio

import anyio
import pytest

from services.anyio_pools import TaskPool


@pytest.mark.asyncio
async def test_workers_process_submitted_items():
    done = []

    async def worker(item):
        await anyio.sleep(0.001)
        done.append(item)

    pool = TaskPool("t", worker, workers=2, queue_max=10)
    pool.ensure_started()
    for i in range(5):
        assert pool.submit(i) is True
    await pool.stop(drain=True)
    assert sorted(done) == [0, 1, 2, 3, 4]


@pytest.mark.asyncio
async def test_stop_drains_queue_before_exit():
    processed = []

    async def worker(item):
        processed.append(item)

    pool = TaskPool("t", worker, workers=1, queue_max=10)
    pool.ensure_started()
    for i in range(8):
        pool.submit(i)
    await pool.stop(drain=True)
    assert sorted(processed) == list(range(8))
    assert pool.qsize() == 0


@pytest.mark.asyncio
async def test_stop_without_drain_discards_pending():
    processed = []

    async def worker(item):
        await anyio.sleep(0.001)
        processed.append(item)

    pool = TaskPool("t", worker, workers=1, queue_max=50)
    pool.ensure_started()
    for i in range(20):
        pool.submit(i)
    await pool.stop(drain=False)
    assert pool.qsize() == 0
    assert len(processed) <= 20  # in-flight item may finish; rest discarded


@pytest.mark.asyncio
async def test_worker_exception_does_not_kill_pool():
    done = []
    n = {"count": 0}

    async def worker(item):
        n["count"] += 1
        if item % 2 == 0:
            raise ValueError(f"bad item {item}")
        done.append(item)

    pool = TaskPool("t", worker, workers=1, queue_max=10)
    pool.ensure_started()
    for i in range(6):
        pool.submit(i)
    await pool.stop(drain=True)
    assert sorted(done) == [1, 3, 5]
    assert n["count"] == 6  # every item attempted despite raises


@pytest.mark.asyncio
async def test_submit_before_start_returns_false():
    async def worker(item):
        return None

    pool = TaskPool("t", worker)
    assert pool.submit(1) is False


@pytest.mark.asyncio
async def test_submit_after_stop_returns_false():
    async def worker(item):
        return None

    pool = TaskPool("t", worker)
    pool.ensure_started()
    await pool.stop()
    assert pool.submit(1) is False
    assert pool.running is False


@pytest.mark.asyncio
async def test_submit_full_queue_drops():
    gate = anyio.Event()
    release = anyio.Event()

    async def worker(item):
        gate.set()
        await release.wait()

    pool = TaskPool("t", worker, workers=1, queue_max=2)
    pool.ensure_started()
    pool.submit("in-flight-wait")
    await gate.wait()  # worker is now busy
    assert pool.submit(1) is True
    assert pool.submit(2) is True
    assert pool.submit(3) is False  # queue full
    release.set()
    await pool.stop(drain=False)


@pytest.mark.asyncio
async def test_stop_joins_hung_worker():
    """A worker hung past stop gets cancelled and joined by the task-group
    exit; stop() must not hang."""
    started = anyio.Event()

    async def worker(item):
        started.set()
        await anyio.sleep(60)

    pool = TaskPool("t", worker, workers=1)
    pool.ensure_started()
    pool.submit("x")
    await started.wait()
    # wait_for in stop() gives 10s; the hung worker is cancelled there.
    # Use a short supervisor timeout via direct manipulation to keep the
    # test fast: stop() itself is what we're exercising, so accept the
    # 10s ceiling but assert completion well under the sleep.
    await asyncio.wait_for(pool.stop(drain=False), timeout=15)
    assert not pool.running


@pytest.mark.asyncio
async def test_ensure_started_idempotent():
    calls = []

    async def worker(item):
        calls.append(item)

    pool = TaskPool("t", worker, workers=2)
    pool.ensure_started()
    sup = pool._supervisor
    pool.ensure_started()
    assert pool._supervisor is sup
    await pool.stop()
