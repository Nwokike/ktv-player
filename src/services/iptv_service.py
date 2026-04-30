import re
import asyncio
import httpx
from database.manager import db_manager
from channels.provider import channel_provider


class IPTVService:
    def __init__(self):
        self._http_client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        return self._http_client

    async def fetch_built_in_channels(self):
        return await asyncio.to_thread(channel_provider.get_all_channels)

    async def _parse_m3u_from_url(self, url: str) -> list[dict]:
        try:
            client = self._get_client()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            }
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return self._parse_m3u_text(resp.text)
        except Exception:
            return []

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
                group = "Custom"

                logo_match = re.search(r'tvg-logo="([^"]*)"', meta)
                if logo_match:
                    logo = logo_match.group(1)

                group_match = re.search(r'group-title="([^"]*)"', meta)
                if group_match:
                    group = group_match.group(1) or "Custom"

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

    async def fetch_playlist(self, url: str) -> list[dict]:
        return await self._parse_m3u_from_url(url)

    async def load_all_sources(self):
        built_in = await self.fetch_built_in_channels()
        all_channels = list(built_in)

        playlists = await db_manager.get_playlists()
        active_playlists = [p for p in playlists if p["is_active"]]

        if active_playlists:
            tasks = [self.fetch_playlist(p["url"]) for p in active_playlists]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for p, ext_channels in zip(active_playlists, results):
                if isinstance(ext_channels, list):
                    for c in ext_channels:
                        c["group"] = p["name"]
                        c["is_custom"] = True
                    all_channels.extend(ext_channels)

        custom_channels = await db_manager.get_custom_channels()
        for c in custom_channels:
            c["is_custom"] = True
            if not c.get("group"):
                c["group"] = "Custom"
        all_channels.extend(custom_channels)

        return all_channels

    async def close(self):
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()


iptv_service = IPTVService()
