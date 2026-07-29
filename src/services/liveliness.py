import time
from collections import OrderedDict
from collections.abc import Callable


class LivelinessCache:
    def __init__(self, max_size: int = 500, ttl: int = 300):
        self._cache: OrderedDict[str, tuple[bool, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._dirty: list[tuple[str, bool, int]] = []
        self._on_change: Callable[[], None] | None = None

    def set_on_change(self, callback: Callable[[], None]) -> None:
        """Register a callback that fires when liveliness results arrive."""
        self._on_change = callback

    def get(self, url: str) -> bool | None:
        entry = self._cache.get(url)
        if entry is None:
            return None
        is_live, timestamp = entry
        if time.time() - timestamp > self._ttl:
            del self._cache[url]
            return None
        return is_live

    def set(self, url: str, is_live: bool):
        now = time.time()
        if url in self._cache:
            self._cache.move_to_end(url)
        elif len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
        self._cache[url] = (is_live, now)
        self._dirty.append((url, is_live, int(now)))
        if self._on_change:
            try:
                self._on_change()
            except Exception:
                pass

    def clear(self):
        self._cache.clear()
        self._dirty.clear()

    def drain_dirty(self) -> list[tuple[str, bool, int]]:
        batch = self._dirty
        self._dirty = []
        return batch

    def load_from_db(self, entries: dict[str, tuple[bool, float]]):
        now = time.time()
        for url, (is_live, ts) in entries.items():
            if now - ts < self._ttl:
                if len(self._cache) >= self._max_size:
                    break
                self._cache[url] = (is_live, ts)


liveliness_cache = LivelinessCache()
