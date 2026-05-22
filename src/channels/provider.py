import asyncio
import logging
import os
import time

from services.http_client import get_http_client
from services.m3u_parser import parse_m3u_text

logger = logging.getLogger(__name__)

_CACHE_DIR = os.path.join("storage", "data")
_CACHE_FILE = os.path.join(_CACHE_DIR, "cached_playlist.m3u8")

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
    for c in channels:
        category = c.get("group", "General")
        is_country = not any(cat in category.lower() for cat in NON_COUNTRY_GROUPS)
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
            return self._channels

        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            cached_text = _read_cache_file()
            should_refresh = True

            if cached_text:
                file_age = time.time() - os.path.getmtime(_CACHE_FILE)
                if file_age < self.CACHE_DURATION:
                    # Fresh cache — use it, no refresh needed
                    self._channels = self._parse_cached(cached_text)
                    return self._channels
                elif file_age < self.STALE_DURATION:
                    # Stale but usable — serve it, then try refresh
                    self._channels = self._parse_cached(cached_text)
                    should_refresh = True

            if should_refresh:
                refresh_lock = await self._get_refresh_lock()
                if refresh_lock.locked():
                    await asyncio.sleep(0.5)
                    return self._channels

                async with refresh_lock:
                    if self._channels:
                        return self._channels
                    try:
                        client = get_http_client()
                        response = await client.get(self.MASTER_PLAYLIST_URL)
                        response.raise_for_status()
                        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
                            f.write(response.text)
                        self._channels = self._parse_cached(response.text)
                    except Exception:
                        logger.exception("Failed to fetch master playlist")
                        # Fallback to cache if available
                        if not self._channels and cached_text:
                            self._channels = self._parse_cached(cached_text)

        except Exception:
            logger.exception("Error in get_all_channels")

        return self._channels

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
