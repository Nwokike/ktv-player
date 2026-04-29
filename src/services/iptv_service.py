import asyncio
import httpx
import os
import uuid
from m3u_parser import M3uParser
from typing import List, Dict
from database.manager import db_manager
from channels.provider import channel_provider
from channels.base import ChannelData


class IPTVService:
    def __init__(self):
        # STEALTH: Spoof a generic Chrome/Windows browser to bypass Cloudflare 403 Forbidden blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0, connect=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True,
            headers=headers,
        )

    async def fetch_built_in_channels(self):
        # Pushing to thread to prevent importlib from blocking the Flet event loop on startup
        channels = await asyncio.to_thread(channel_provider.get_all_channels)
        return [self._channel_to_dict(c) for c in channels]

    def _channel_to_dict(self, c: ChannelData) -> Dict:
        return {
            "name": c.name,
            "url": c.url,
            "logo": c.logo,
            "group": c.group,
            "country_code": c.country_code,
            "epg_id": c.epg_id,
        }

    def _parse_playlist_sync(self, content: str) -> List[Dict]:
        """Synchronous parser isolated to prevent Flet UI blocking."""
        parser = M3uParser()
        # Use UUID to prevent file locking issues during concurrent fetching
        temp_file = f"temp_playlist_{uuid.uuid4().hex}.m3u"

        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)

            parser.parse_m3u(temp_file)
            return parser.get_list()
        except Exception as e:
            print(f"Parsing error: {e}")
            return []
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    async def fetch_playlist(self, url: str) -> List[Dict]:
        try:
            response = await self.client.get(url)
            response.raise_for_status()

            # Execute disk I/O and parsing completely off the main thread
            channels = await asyncio.to_thread(self._parse_playlist_sync, response.text)
            return channels
        except Exception as e:
            print(f"Network error fetching playlist {url}: {e}")
            return []

    async def load_all_sources(self):
        built_in = await self.fetch_built_in_channels()
        all_channels = built_in

        playlists = await db_manager.get_playlists()
        active_playlists = [p for p in playlists if p["is_active"]]

        if active_playlists:
            tasks = [self.fetch_playlist(p["url"]) for p in active_playlists]
            # return_exceptions=True prevents one bad/dead URL from crashing the rest of the playlist downloads
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for p, ext_channels in zip(active_playlists, results):
                if isinstance(ext_channels, list):
                    # Tag with playlist name as group and mark as custom
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
        await self.client.aclose()


# Global instance
iptv_service = IPTVService()
