import asyncio
import contextlib
import logging

import anyio
import httpx

from core.state import state
from services.anyio_pools import TaskPool
from services.http_client import get_http_client
from services.liveliness import liveliness_cache

logger = logging.getLogger(__name__)


_in_flight: set[str] = set()
_pool: TaskPool | None = None

# Shared across ALL checker instances (worker probes + concurrent check_single
# callers): the old per-instance Semaphore(4) let 2 workers + N batch callers
# run 8-12 concurrent probes against a pool that times out in 2s — exhaustion
# painted dots red.
_PROBE_SEMAPHORE = asyncio.Semaphore(4)

# Observability without painting dots: how many probes died to local pool
# exhaustion (vs genuinely dead streams). Read via pool_timeouts().
_pool_timeouts = 0

_WORKERS = 4
_QUEUE_MAX = 500


def _get_pool() -> TaskPool:
    global _pool
    if _pool is None:
        _pool = TaskPool(
            "liveliness",
            _probe_and_persist,
            workers=_WORKERS,
            queue_max=_QUEUE_MAX,
        )
    return _pool


def pool_timeouts() -> int:
    return _pool_timeouts


async def _probe_and_persist(url: str) -> None:
    """Probe one URL, then persist dirty verdicts.

    The persist step runs under a SHIELDED cancel scope: app shutdown
    cancels the pool mid-probe, and without the shield the save_batch
    write would be dropped with it (verdicts lost, stale replay on next
    boot).
    """
    try:
        checker = LivelinessChecker(None)
        await checker.check_single(url)
        dirty = liveliness_cache.drain_dirty()
        if dirty:
            from services.liveliness_store import save_batch

            with anyio.CancelScope(shield=True):
                await save_batch(dirty)
    except asyncio.CancelledError:
        # Persist what the cancelled probe already decided, then re-raise
        # so the task-group join sees a clean cancellation.
        dirty = liveliness_cache.drain_dirty()
        if dirty:
            from services.liveliness_store import save_batch

            with anyio.CancelScope(shield=True):
                await save_batch(dirty)
        raise
    finally:
        _in_flight.discard(url)


def _ensure_queue():
    _get_pool().ensure_started()


def drain_queue():
    """Clear all pending items from the liveliness queue."""
    queue = _get_pool()._queue
    if queue is None:
        return
    while True:
        try:
            queue.get_nowait()
            queue.task_done()
        except asyncio.QueueEmpty:
            break
    _in_flight.clear()


def shutdown_workers():
    """Sync emergency stop: cancel the pool supervisor (workers are
    cancelled and joined by its task-group exit once the loop runs).

    Prefer :func:`ashutdown_workers` in async contexts (app close) — it
    drains first and awaits the join, so no queued probe or in-flight
    persist is dropped.
    """
    global _pool
    if _pool is not None and _pool._supervisor is not None:
        _pool._supervisor.cancel()
    _pool = None
    _in_flight.clear()


async def ashutdown_workers():
    """Drain the queue, then stop + join the worker pool (no lost
    verdicts, no stale replay on restart)."""
    global _pool
    if _pool is not None:
        await _pool.stop(drain=True)
    _pool = None
    _in_flight.clear()


def enqueue_liveliness_check(url: str):
    if not url or liveliness_cache.get(url) is not None:
        return
    if url in _in_flight:
        return
    # No probes while offline — a failed probe would paint the dot red;
    # dots stay neutral and checks resume when connectivity returns.
    if not state.is_online:
        return

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("Liveliness enqueue with no running loop for %s", url)
        return

    _ensure_queue()
    _in_flight.add(url)
    if not _get_pool().submit(url):
        _in_flight.discard(url)


def _is_live_status(status_code: int) -> bool:
    """Single unified live predicate (HEAD and GET paths agreed)."""
    return 200 <= status_code < 400


class LivelinessChecker:
    def __init__(self, page_obj=None):
        self.page_obj = page_obj

    def _get_http_client(self) -> httpx.AsyncClient:
        return get_http_client()

    async def check_single(self, url: str) -> tuple[str, bool | None]:
        """Probe one URL. Returns (url, True/False) for remote verdicts,
        (url, None) for UNKNOWN (offline, pool exhaustion, local errors) —
        unknown never touches the cache and never paints a dot."""
        global _pool_timeouts
        cached = liveliness_cache.get(url)
        if cached is not None:
            return (url, cached)

        # Offline: unknown, not dead. (The old `return (url, False)` painted
        # every dot red whenever the radio dropped.)
        if not state.is_online:
            return (url, None)

        if not url or not isinstance(url, str):
            return (url, None)

        check_timeout = httpx.Timeout(2.0, connect=1.2, read=2.5, write=2.0, pool=2.0)
        async with _PROBE_SEMAPHORE:
            try:
                client = self._get_http_client()
            except Exception:
                return (url, None)
            try:
                try:
                    resp = await client.head(url, timeout=check_timeout)
                    # 405/501 mean the server refuses HEAD — not that the
                    # stream is down. Retry as a ranged GET before calling
                    # the channel offline. Nothing else retries: a timeout is
                    # already a full-budget verdict, not a HEAD quirk.
                    if resp.status_code in (405, 501):
                        resp = await self._ranged_get(client, url, check_timeout)
                    is_live = _is_live_status(resp.status_code)
                except (httpx.PoolTimeout, TimeoutError) as ex:
                    # Local exhaustion, not a dead stream: unknown + count it.
                    # (The old code retried as GET then cached False — pool
                    # pressure painted healthy streams red.)
                    _pool_timeouts += 1
                    logger.debug("Liveliness pool timeout for %s: %s", url, ex)
                    return (url, None)
                except httpx.ConnectError:
                    # Middleboxes that block HEAD: one ranged-GET chance.
                    try:
                        resp = await self._ranged_get(client, url, check_timeout)
                    except Exception:
                        return await self._remote_fail(url)
                    is_live = _is_live_status(resp.status_code)
                liveliness_cache.set(url, is_live)
                return (url, is_live)
            except (httpx.PoolTimeout, TimeoutError):
                _pool_timeouts += 1
                return (url, None)
            except RuntimeError:
                # Closed client / dead loop: local failure, not a verdict.
                return (url, None)
            except asyncio.CancelledError:
                raise
            except Exception:
                return await self._remote_fail(url)

    async def _ranged_get(self, client, url: str, timeout):
        """One-chunk ranged GET: proves servability without downloading.

        Streamed (not buffered): a Range-ignoring server + non-streaming GET
        downloads the entire file into memory (OOM on direct-MP4 URLs).
        """
        async with client.stream(
            "GET", url, headers={"Range": "bytes=0-0"}, timeout=timeout
        ) as resp:
            async for _ in resp.aiter_bytes(1024):
                break
            return resp

    async def _remote_fail(self, url: str) -> tuple[str, bool]:
        """Definitive remote failure (connection refused, DNS, remote timeout
        after budget): cache dead, paint red."""
        with contextlib.suppress(Exception):
            liveliness_cache.set(url, False)
        return (url, False)

    async def close(self):
        """No-op: the shared client is owned by http_client (shutdown-only
        close at app exit). Kept so callers don't have to care."""
