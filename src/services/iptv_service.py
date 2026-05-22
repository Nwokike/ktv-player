import asyncio
import logging

import httpx

from channels.provider import channel_provider
from database.manager import db_manager
from services.http_client import get_http_client
from services.m3u_parser import parse_m3u_text

logger = logging.getLogger(__name__)


class IPTVService:
    def get_client(self) -> "httpx.AsyncClient":
        return get_http_client()

    async def fetch_built_in_channels(self):
        return await channel_provider.get_all_channels()

    async def _parse_m3u_from_url(self, url: str) -> list[dict]:
        try:
            client = self.get_client()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return parse_m3u_text(resp.text, default_group="Custom")
        except Exception:
            return []

    async def fetch_playlist(self, url: str) -> list[dict]:
        return await self._parse_m3u_from_url(url)

    async def load_all_sources(self):
        built_in = await self.fetch_built_in_channels()
        all_channels = list(built_in)

        playlists = await db_manager.get_playlists()
        active_playlists = [p for p in playlists if p["is_active"]]

        if active_playlists:
            tasks = [self.fetch_playlist(p["url"]) for p in active_playlists]
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=60.0,
                )
            except TimeoutError:
                results = [Exception("Playlist load timeout")] * len(active_playlists)
            for p, ext_channels in zip(active_playlists, results, strict=True):
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
        from services.http_client import close_http_client

        await close_http_client()


iptv_service = IPTVService()
