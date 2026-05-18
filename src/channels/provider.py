import asyncio
import os
import tempfile
import time

import httpx

from services.m3u_parser import parse_m3u_text


class ChannelProvider:
    def __init__(self):
        self.MASTER_PLAYLIST_URL = "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
        self.CACHE_FILE = os.path.join(tempfile.gettempdir(), "cached_playlist.m3u8")
        self.CACHE_DURATION = 24 * 60 * 60
        self.STALE_DURATION = 48 * 60 * 60
        self._channels = []
        self._refresh_lock = None
        self._refresh_in_progress = False

    async def _get_refresh_lock(self):
        if self._refresh_lock is None:
            self._refresh_lock = asyncio.Lock()
        return self._refresh_lock

    def _classify_channels(self, channels: list[dict]) -> list[dict]:
        non_country_groups = {
            "movies", "news", "sports", "documentaries", "music",
            "kids", "comedy", "vod", "business", "weather",
            "lifestyle", "religious", "education", "general",
        }
        for c in channels:
            category = c.get("group", "General")
            is_country = not any(cat in category.lower() for cat in non_country_groups)
            c["country_code"] = "M3U" if is_country else ""
            c["is_custom"] = False
        return channels

    async def get_all_channels(self) -> list[dict]:
        if self._channels:
            return self._channels

        try:
            has_cache = os.path.exists(self.CACHE_FILE)
            should_refresh = True

            if has_cache:
                file_age = time.time() - os.path.getmtime(self.CACHE_FILE)
                if file_age < self.CACHE_DURATION:
                    should_refresh = False
                elif file_age < self.STALE_DURATION:
                    with open(self.CACHE_FILE, encoding="utf-8") as f:
                        text = f.read()
                    self._channels = self._classify_channels(parse_m3u_text(text, default_group="General"))
                    should_refresh = True
                else:
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
                        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                            response = await client.get(self.MASTER_PLAYLIST_URL)
                            response.raise_for_status()
                        with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                            f.write(response.text)
                        text = response.text
                        self._channels = self._classify_channels(parse_m3u_text(text, default_group="General"))
                    except Exception:
                        if not self._channels and has_cache:
                            with open(self.CACHE_FILE, encoding="utf-8") as f:
                                text = f.read()
                            self._channels = self._classify_channels(parse_m3u_text(text, default_group="General"))
            elif has_cache:
                with open(self.CACHE_FILE, encoding="utf-8") as f:
                    text = f.read()
                self._channels = self._classify_channels(parse_m3u_text(text, default_group="General"))

        except Exception:
            pass

        return self._channels

    def get_countries(self) -> list[dict]:
        channels = self._channels
        if not channels:
            try:
                has_cache = os.path.exists(self.CACHE_FILE)
                if has_cache:
                    with open(self.CACHE_FILE, encoding="utf-8") as f:
                        text = f.read()
                    channels = self._classify_channels(parse_m3u_text(text, default_group="General"))
            except Exception:
                pass
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
