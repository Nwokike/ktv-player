import os
import re
import time
import tempfile
import httpx


class ChannelProvider:
    def __init__(self):
        self.MASTER_PLAYLIST_URL = "https://raw.githubusercontent.com/Nwokike/IPTV/master/playlist.m3u8"
        self.CACHE_FILE = os.path.join(tempfile.gettempdir(), "cached_playlist.m3u8")
        self.CACHE_DURATION = 24 * 60 * 60
        self._channels = []

    def _parse_m3u_text(self, text: str) -> list[dict]:
        channels = []
        lines = text.strip().splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("#EXTINF:"):
                meta = line
                name = meta.rsplit(",", 1)[-1].strip() if "," in meta else "Unknown"
                logo = ""
                group = "General"

                logo_match = re.search(r'tvg-logo="([^"]*)"', meta)
                if logo_match:
                    logo = logo_match.group(1)

                group_match = re.search(r'group-title="([^"]*)"', meta)
                if group_match:
                    group = group_match.group(1) or "General"

                i += 1
                while i < len(lines) and lines[i].strip().startswith("#"):
                    i += 1

                if i < len(lines):
                    url = lines[i].strip()
                    if url and not url.startswith("#"):
                        channels.append({
                            "name": name,
                            "url": url,
                            "logo": logo or "/icon.png",
                            "group": group,
                        })
            i += 1
        return channels

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

    def get_all_channels(self) -> list[dict]:
        if self._channels:
            return self._channels

        try:
            should_download = True
            if os.path.exists(self.CACHE_FILE):
                file_age = time.time() - os.path.getmtime(self.CACHE_FILE)
                if file_age < self.CACHE_DURATION:
                    should_download = False

            if should_download:
                response = httpx.get(
                    self.MASTER_PLAYLIST_URL,
                    timeout=15.0,
                    follow_redirects=True,
                )
                response.raise_for_status()
                with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(response.text)

            with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                text = f.read()

            self._channels = self._classify_channels(self._parse_m3u_text(text))

        except Exception:
            pass

        return self._channels

    def get_countries(self) -> list[dict]:
        channels = self.get_all_channels()
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
