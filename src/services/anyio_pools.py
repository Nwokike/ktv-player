"""Anyio worker pool on the Flet-owned event loop.

Verified against installed anyio 4.15.1: task groups and cancel scopes
work on any running asyncio loop — no ``anyio.run`` and no second thread
required. That matters here because every worker shares the httpx client
from ``services.http_client``, which is bound to the Flet loop; running
workers on a second loop/thread would break it.

A :class:`TaskPool` gives a worker pool structured concurrency:

- workers start inside one task group (``start_soon``);
- ``stop()`` sets the stop event, lets workers finish their current item
  and exit cleanly, then the task-group exit cancels + JOINS anything
  still running — shutdown can never orphan a task;
- the queue is bounded and non-blocking (``put_nowait`` + drop), as the
  previous implementation guaranteed.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import anyio

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TaskPool:
    """Bounded queue + N workers under one anyio task group."""

    def __init__(
        self,
        name: str,
        worker: Callable[[T], Awaitable[None]],
        *,
        workers: int = 4,
        queue_max: int = 500,
    ) -> None:
        self._name = name
        self._worker_fn = worker
        self._worker_count = workers
        self._queue_max = queue_max
        self._queue: asyncio.Queue[T] | None = None
        self._stop_event: anyio.Event | None = None
        self._supervisor: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._supervisor is not None and not self._supervisor.done()

    def ensure_started(self) -> None:
        """Start workers if not running. Must be called from the loop."""
        if self.running:
            return
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=self._queue_max)
        self._stop_event = anyio.Event()
        self._supervisor = asyncio.get_running_loop().create_task(
            self._supervise(), name=f"{self._name}-supervisor"
        )

    async def _supervise(self) -> None:
        stop = self._stop_event
        assert stop is not None
        async with anyio.create_task_group() as tg:
            for i in range(self._worker_count):
                tg.start_soon(self._worker_loop, i)
            # Hold the group open until stop(); exiting the context
            # cancels and joins any worker still mid-item.
            await stop.wait()

    async def _worker_loop(self, index: int) -> None:
        queue = self._queue
        assert queue is not None
        stop = self._stop_event
        assert stop is not None
        while True:
            if stop.is_set() and queue.empty():
                # Stop requested and nothing left to drain.
                return
            try:
                item = queue.get_nowait()
            except asyncio.QueueEmpty:
                if stop.is_set():
                    return
                # Block for the next item, but wake immediately on stop.
                getter = asyncio.ensure_future(queue.get())
                stopper = asyncio.ensure_future(_wait_event(stop))
                try:
                    await asyncio.wait(
                        {getter, stopper},
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                except asyncio.CancelledError:
                    # Worker cancelled mid-wait (sync shutdown path): reap
                    # both futures or they orphan in queue._getters and a
                    # later put_nowait is swallowed.
                    getter.cancel()
                    stopper.cancel()
                    await asyncio.gather(getter, stopper, return_exceptions=True)
                    raise
                finally:
                    stopper.cancel()
                if getter.done() and not getter.cancelled():
                    # The getter completed (possibly in the same instant stop
                    # fired): process the item instead of dropping it.
                    try:
                        item = getter.result()
                    finally:
                        await asyncio.gather(stopper, return_exceptions=True)
                else:
                    getter.cancel()
                    await asyncio.gather(getter, stopper, return_exceptions=True)
                    continue  # one more pass to drain whatever arrived
            try:
                await self._worker_fn(item)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "%s worker %d failed on %r", self._name, index, item
                )
            finally:
                queue.task_done()

    def submit(self, item: T) -> bool:
        """Queue one item without blocking. Returns False when the pool is
        not running or the queue is full (caller decides whether that is
        worth logging)."""
        queue = self._queue
        if queue is None or not self.running:
            return False
        try:
            queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            return False

    def qsize(self) -> int:
        return self._queue.qsize() if self._queue is not None else 0

    async def stop(self, *, drain: bool = True) -> None:
        """Stop workers. With ``drain`` (default), items already queued are
        processed before workers exit; without it, the queue is cleared.
        Either way, an in-flight item finishes (or is cancelled and joined
        by the task-group exit) — nothing is orphaned."""
        supervisor = self._supervisor
        if supervisor is None:
            return
        self._supervisor = None
        if not drain and self._queue is not None:
            while True:
                try:
                    self._queue.get_nowait()
                    self._queue.task_done()
                except asyncio.QueueEmpty:
                    break
        if self._stop_event is not None:
            self._stop_event.set()
        try:
            await asyncio.wait_for(supervisor, timeout=10.0)
        except TimeoutError:
            logger.warning("%s pool shutdown timed out; cancelling", self._name)
            supervisor.cancel()
            await asyncio.gather(supervisor, return_exceptions=True)
        except asyncio.CancelledError:
            supervisor.cancel()
            await asyncio.gather(supervisor, return_exceptions=True)
            raise


async def _wait_event(event: anyio.Event) -> None:
    await event.wait()
