import contextlib
import logging
import time
from collections import OrderedDict
from collections.abc import Callable

logger = logging.getLogger(__name__)


class LivelinessCache:
    def __init__(self, max_size: int = 500, ttl: int = 300):
        self._cache: OrderedDict[str, tuple[bool, float]] = OrderedDict()
        self._max_size = max(1, int(max_size))
        self._ttl = max(0, ttl)
        self._dirty: list[tuple[str, bool, int]] = []
        self._subscribers: list[Callable[[str | None], None]] = []

    def add_on_change(
        self, callback: Callable[[str | None], None]
    ) -> Callable[[], None]:
        """Subscribe to liveliness results. Returns an unsubscriber.

        Multi-subscriber: Home, Search and ChannelGrid each listen without
        clobbering each other (the old single slot meant mounting Search
        froze Home's dots, and unmounting never restored them).
        """
        self._subscribers.append(callback)

        def _unsubscribe() -> None:
            with contextlib.suppress(ValueError):
                self._subscribers.remove(callback)

        return _unsubscribe

    def remove_on_change(self, callback: Callable[[str | None], None]) -> None:
        with contextlib.suppress(ValueError):
            self._subscribers.remove(callback)

    def _notify(self, url: str | None) -> None:
        for cb in list(self._subscribers):
            try:
                cb(url)
            except Exception:
                logger.debug("Liveliness subscriber failed", exc_info=True)

    def get(self, url: str) -> bool | None:
        entry = self._cache.get(url)
        if entry is None:
            return None
        is_live, timestamp = entry
        if time.time() - timestamp > self._ttl:
            del self._cache[url]
            return None
        # True LRU: reads refresh recency so hot entries aren't evicted by
        # cold writes.
        self._cache.move_to_end(url)
        return is_live

    def set(self, url: str, is_live: bool):
        if not url or not isinstance(is_live, bool):
            return
        now = time.time()
        if url in self._cache:
            self._cache.move_to_end(url)
        elif len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
        self._cache[url] = (is_live, now)
        self._dirty.append((url, is_live, int(now)))
        # Bound the dirty queue: undrained duplicates previously grew it
        # without limit and forced redundant DB writes.
        if len(self._dirty) > 5000:
            del self._dirty[: len(self._dirty) - 5000]
        self._notify(url)

    def clear(self):
        self._cache.clear()
        self._dirty.clear()
        self._notify(None)

    def drain_dirty(self) -> list[tuple[str, bool, int]]:
        batch = self._dirty
        self._dirty = []
        return batch

    def load_from_db(self, entries: dict[str, tuple[bool, float]]):
        now = time.time()
        # Newest first so the freshest verdicts win the size cap; overwrites
        # of an existing URL don't consume capacity.
        try:
            ordered = sorted(entries.items(), key=lambda kv: kv[1][1], reverse=True)
        except Exception:
            ordered = list(entries.items())
        for url, value in ordered:
            try:
                is_live, ts = value
                is_live = bool(is_live)
                ts = float(ts)
            except (TypeError, ValueError):
                continue
            if now - ts > self._ttl:
                continue
            if url in self._cache:
                self._cache[url] = (is_live, ts)
                self._cache.move_to_end(url)
            else:
                if len(self._cache) >= self._max_size:
                    continue
                self._cache[url] = (is_live, ts)


liveliness_cache = LivelinessCache()
