import asyncio
import logging

import httpx

from core.constants import (
    LIVELINESS_BATCH_SIZE,
    LIVELINESS_UPDATE_INTERVAL,
)
from core.state import state
from core.theme import AppColors
from services.http_client import get_http_client
from services.liveliness import liveliness_cache

logger = logging.getLogger(__name__)


_in_flight: set[str] = set()
_liveliness_queue: asyncio.Queue[str] | None = None
_worker_tasks: list[asyncio.Task] = []
_workers_started = False

_WORKERS = 2
_QUEUE_MAX = 500


async def _liveliness_worker():
    checker = LivelinessChecker(None)
    while True:
        try:
            url = await _liveliness_queue.get()
            try:
                await checker.check_single(url)
                dirty = liveliness_cache.drain_dirty()
                if dirty:
                    from database.manager import db_manager

                    await db_manager.save_liveliness_batch(dirty)
            except Exception:
                logger.exception("Liveliness check failed for %s", url)
            finally:
                _liveliness_queue.task_done()
                _in_flight.discard(url)
        except Exception:
            await asyncio.sleep(1)


def _ensure_queue():
    global _liveliness_queue, _workers_started
    if _liveliness_queue is None:
        _liveliness_queue = asyncio.Queue(maxsize=_QUEUE_MAX)
    if not _workers_started:
        try:
            loop = asyncio.get_running_loop()
            _workers_started = True
            for _ in range(_WORKERS):
                _worker_tasks.append(loop.create_task(_liveliness_worker()))
        except RuntimeError:
            pass


def drain_queue():
    """Clear all pending items from the liveliness queue."""
    if _liveliness_queue is None:
        return
    while not _liveliness_queue.empty():
        try:
            _liveliness_queue.get_nowait()
            _liveliness_queue.task_done()
        except asyncio.QueueEmpty:
            break
    _in_flight.clear()


def shutdown_workers():
    """Cancel all background liveliness workers. Call on app exit."""
    for task in _worker_tasks:
        if not task.done():
            task.cancel()
    _worker_tasks.clear()


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
        return

    _ensure_queue()
    _in_flight.add(url)
    try:
        _liveliness_queue.put_nowait(url)
    except asyncio.QueueFull:
        _in_flight.discard(url)


class LivelinessChecker:
    def __init__(self, page_obj=None):
        self.page_obj = page_obj
        self._semaphore = asyncio.Semaphore(4)

    def _get_http_client(self) -> httpx.AsyncClient:
        return get_http_client()

    async def check_single(self, url: str) -> tuple[str, bool]:
        cached = liveliness_cache.get(url)
        if cached is not None:
            return (url, cached)

        # Offline: skip the probe entirely and leave the dot neutral
        if not state.is_online:
            return (url, False)

        check_timeout = httpx.Timeout(2.0, connect=1.2, read=1.0)
        async with self._semaphore:
            try:
                client = self._get_http_client()
                try:
                    resp = await client.head(url, timeout=check_timeout)
                    is_live = resp.status_code < 400
                except Exception:
                    resp = await client.get(
                        url,
                        headers={"Range": "bytes=0-0"},
                        timeout=check_timeout,
                    )
                    is_live = resp.status_code in (200, 206, 301, 302, 304)
                liveliness_cache.set(url, is_live)
                return (url, is_live)
            except Exception:
                liveliness_cache.set(url, False)
                return (url, False)

    async def fire_batch(self, cards_data: list):
        for i in range(0, len(cards_data), LIVELINESS_BATCH_SIZE):
            batch = cards_data[i : i + LIVELINESS_BATCH_SIZE]
            tasks = [self.check_single(cd["url"]) for cd in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for cd, result in zip(batch, results, strict=True):
                if isinstance(result, tuple):
                    _, is_live = result
                    if "indicator" in cd and hasattr(cd["indicator"], "bgcolor"):
                        cd["indicator"].bgcolor = (
                            AppColors.SUCCESS if is_live else AppColors.ERROR
                        )

            batch_num = i // LIVELINESS_BATCH_SIZE
            is_last = (i + LIVELINESS_BATCH_SIZE) >= len(cards_data)
            if self.page_obj and (
                is_last or (batch_num % LIVELINESS_UPDATE_INTERVAL == 0)
            ):
                try:
                    self.page_obj.update()
                except Exception:
                    pass

            if not is_last:
                await asyncio.sleep(0.05)

        # Persist dirty cache entries to DB
        dirty = liveliness_cache.drain_dirty()
        if dirty:
            from database.manager import db_manager

            await db_manager.save_liveliness_batch(dirty)

    async def close(self):
        pass
