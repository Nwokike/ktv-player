import asyncio
import httpx
from m3u_parser import M3uParser
from typing import List, Dict, Optional
import os
from database.manager import db_manager
from channels.provider import channel_provider
from channels.base import ChannelData

class IPTVService:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True
        )
        self.cache_file = "channels_cache.json"

    async def fetch_built_in_channels(self):
        """Loads channels from the modular python files."""
        channels = channel_provider.get_all_channels()
        # Convert to dict format for state
        return [self._channel_to_dict(c) for c in channels]

    def _channel_to_dict(self, c: ChannelData) -> Dict:
        return {
            "name": c.name,
            "url": c.url,
            "logo": c.logo,
            "group": c.group,
            "country_code": c.country_code,
            "epg_id": c.epg_id
        }

    async def fetch_playlist(self, url: str) -> List[Dict]:
        """
        Fetches and parses an M3U playlist.
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            parser = M3uParser()
            temp_file = "temp_playlist.m3u"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(response.text)
            
            await asyncio.to_thread(parser.parse_m3u, temp_file)
            channels = parser.get_list()
            
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            return channels
        except Exception as e:
            print(f"Error fetching playlist: {e}")
            return []

    async def load_all_sources(self):
        """Main entry point to load all channels into state with parallel fetching."""
        # Start fetching built-in channels (very fast)
        built_in = await self.fetch_built_in_channels()
        all_channels = built_in
        
        # Load custom playlists from DB in parallel
        playlists = await db_manager.get_playlists()
        active_playlist_urls = [p["url"] for p in playlists if p["is_active"]]
        
        if active_playlist_urls:
            # Fetch all active playlists concurrently
            tasks = [self.fetch_playlist(url) for url in active_playlist_urls]
            results = await asyncio.to_thread(asyncio.run, asyncio.gather(*tasks)) if not asyncio.get_event_loop().is_running() else await asyncio.gather(*tasks)
            for ext_channels in results:
                all_channels.extend(ext_channels)
        
        # Load individual custom channels from DB
        custom_channels = await db_manager.get_custom_channels()
        all_channels.extend(custom_channels)
        
        return all_channels

    async def close(self):
        await self.client.aclose()

# Global instance
iptv_service = IPTVService()
