import time


class LivelinessCache:
    def __init__(self, max_size: int = 500, ttl: int = 300):
        self._cache: dict[str, tuple[bool, float]] = {}
        self._max_size = max_size
        self._ttl = ttl

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
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]
        self._cache[url] = (is_live, time.time())

    def clear(self):
        self._cache.clear()


liveliness_cache = LivelinessCache()
