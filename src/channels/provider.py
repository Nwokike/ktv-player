import asyncio
import contextlib
import logging
import os
import tempfile
import time

from services.http_client import get_http_client
from services.m3u_parser import parse_m3u_text

logger = logging.getLogger(__name__)

_cache_env = os.getenv("FLET_APP_STORAGE_CACHE")
_CACHE_DIR = (
    os.path.join(_cache_env, "data") if _cache_env else os.path.join("storage", "data")
)
_CACHE_FILE = os.path.join(_CACHE_DIR, "cached_playlist.m3u8")


def _write_cache(text: str) -> None:
    """Write playlist text to cache file atomically (tmp + rename)."""
    os.makedirs(_CACHE_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=_CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_path, _CACHE_FILE)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


NON_COUNTRY_GROUPS = {
    "movies",
    "news",
    "sports",
    "documentaries",
    "music",
    "kids",
    "comedy",
    "vod",
    "business",
    "weather",
    "lifestyle",
    "religious",
    "education",
    "general",
}


def _classify_channels(channels: list[dict]) -> list[dict]:
    import re

    for c in channels:
        category = c.get("group", "General")
        lower = category.lower()
        is_country = not any(
            bool(re.search(rf"(^|\W){cat}(\W|$)", lower)) for cat in NON_COUNTRY_GROUPS
        )
        c["country_code"] = "M3U" if is_country else ""
        c["is_custom"] = False
    return channels


def _read_cache_file() -> str | None:
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, encoding="utf-8") as f:
                return f.read()
    except OSError:
        pass
    return None


class ChannelProvider:
    def __init__(self):
        self.MASTER_PLAYLIST_URL = (
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
        )
        self.PLAYLIST_SOURCES = [
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
            "https://nwokike.github.io/IPTV/playlist.m3u8",
        ]
        self.CACHE_DURATION = 24 * 60 * 60
        self.STALE_DURATION = 48 * 60 * 60
        self._channels = []
        self._refresh_lock = None

    async def _get_refresh_lock(self):
        if self._refresh_lock is None:
            self._refresh_lock = asyncio.Lock()
        return self._refresh_lock

    def _parse_cached(self, text: str) -> list[dict]:
        return _classify_channels(parse_m3u_text(text, default_group="General"))

    async def get_all_channels(self) -> list[dict]:
        if self._channels:
            return list(self._channels)

        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            cached_text = _read_cache_file()
            should_refresh = True

            if cached_text:
                file_age = time.time() - os.path.getmtime(_CACHE_FILE)
                if file_age < self.CACHE_DURATION:
                    # Fresh cache — use it, no refresh needed
                    logger.info(
                        "Using fresh playlist cache (age: %.1f hours)", file_age / 3600
                    )
                    self._channels = self._parse_cached(cached_text)
                    logger.info(
                        "Loaded %d channels from playlist cache", len(self._channels)
                    )
                    return list(self._channels)
                elif file_age < self.STALE_DURATION:
                    # Stale but usable — serve it, then try refresh
                    logger.info(
                        "Playlist cache is stale (age: %.1f hours); serving and refreshing in background",
                        file_age / 3600,
                    )
                    self._channels = self._parse_cached(cached_text)
                    should_refresh = True

            if should_refresh:
                refresh_lock = await self._get_refresh_lock()
                if refresh_lock.locked():
                    await asyncio.sleep(0.5)
                    return list(self._channels)

                async with refresh_lock:
                    if self._channels and not cached_text:
                        return list(self._channels)
                    client = get_http_client()
                    fetched_text = None
                    for url in self.PLAYLIST_SOURCES:
                        try:
                            logger.info("Fetching master playlist from %s", url)
                            response = await client.get(url, timeout=30.0)
                            response.raise_for_status()
                            fetched_text = response.text
                            if fetched_text and len(fetched_text) > 100:
                                break
                        except Exception as ex:
                            logger.warning(
                                "Failed to fetch playlist from %s: %s", url, ex
                            )

                    if fetched_text:
                        await asyncio.to_thread(_write_cache, fetched_text)
                        self._channels = self._parse_cached(fetched_text)
                        logger.info(
                            "Master playlist fetched successfully: %d channels parsed",
                            len(self._channels),
                        )
                    else:
                        # Fallback to cache if available
                        if not self._channels and cached_text:
                            self._channels = self._parse_cached(cached_text)
                            logger.info(
                                "Fallback: loaded %d channels from cached playlist",
                                len(self._channels),
                            )

        except Exception:
            logger.exception("Error in get_all_channels")

        return list(self._channels)

    def get_countries(self) -> list[dict]:
        channels = self._channels
        if not channels:
            cached_text = _read_cache_file()
            if cached_text:
                channels = self._parse_cached(cached_text)

        seen = set()
        countries = []
        for c in channels:
            if c.get("country_code"):
                group = c.get("group", "General")
                name = group.split(";")[0].strip()
                if name and name not in seen:
                    seen.add(name)
                    countries.append({"name": name})
        countries.sort(key=lambda x: x["name"])
        return countries


channel_provider = ChannelProvider()
