import asyncio
from m3u_parser import M3uParser
from typing import List, Dict
from database.manager import db_manager
from channels.provider import channel_provider


class IPTVService:
    def __init__(self):
        pass

    async def fetch_built_in_channels(self):
        # Pushing to thread to prevent blocking the Flet event loop on startup
        channels = await asyncio.to_thread(channel_provider.get_all_channels)
        return [self._channel_to_dict(c) for c in channels]

    def _channel_to_dict(self, c) -> Dict:
        if isinstance(c, dict):
            return c
            
        return {
            "name": getattr(c, "name", "Unknown"),
            "url": getattr(c, "url", ""),
            "logo": getattr(c, "logo", "/icon.png"),
            "group": getattr(c, "group", "Custom"),
            "country_code": getattr(c, "country_code", ""),
            "epg_id": getattr(c, "epg_id", ""),
        }

    def _parse_custom_playlist_sync(self, url: str) -> List[Dict]:
        """Synchronous parser isolated to prevent Flet UI blocking."""
        try:
            # STEALTH: Spoof a generic Chrome browser to bypass Cloudflare 403 blocks
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            parser = M3uParser(timeout=15, useragent=user_agent)
            parser.parse_m3u(url)
            return parser.get_list()
        except Exception as e:
            print(f"Parsing error for {url}: {e}")
            return []

    async def fetch_playlist(self, url: str) -> List[Dict]:
        # Execute network I/O and parsing completely off the main thread
        return await asyncio.to_thread(self._parse_custom_playlist_sync, url)

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
        pass


# Global instance
iptv_service = IPTVService()
