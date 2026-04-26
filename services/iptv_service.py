import asyncio
import httpx
from m3u_parser import M3uParser
from typing import List, Dict, Optional
import json
import os
from database.manager import db_manager

class IPTVService:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            follow_redirects=True
        )
        self.cache_file = "channels_cache.json"

    async def fetch_playlist(self, url: str) -> List[Dict]:
        """
        Fetches and parses an M3U playlist.
        Uses asyncio.to_thread to prevent blocking the Flet event loop.
        """
        try:
            # Step 1: Download the M3U content
            response = await self.client.get(url)
            response.raise_for_status()
            
            # Step 2: Parse using m3u-parser in a separate thread
            parser = M3uParser()
            # We save to a temp file because m3u-parser likes files/urls
            temp_file = "temp_playlist.m3u"
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(response.text)
            
            await asyncio.to_thread(parser.parse_m3u, temp_file)
            channels = parser.get_list()
            
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            return channels
        except Exception as e:
            print(f"Error fetching playlist: {e}")
            return []

    async def get_stream_url_with_fallback(self, channel_id: str, primary_url: str, fallbacks: List[str]) -> Optional[str]:
        """
        Implements the Waterfall logic. 
        Tries the primary URL, then iterates through fallbacks until a working one is found.
        """
        urls = [primary_url] + fallbacks
        for url in urls:
            if await self.is_stream_working(url):
                return url
        return None

    async def is_stream_working(self, url: str) -> bool:
        """
        Quickly checks if a stream URL is reachable.
        """
        try:
            # We only do a HEAD request or a GET with a tiny range to check if it's alive
            async with self.client.stream("GET", url) as response:
                return response.status_code < 400
        except Exception:
            return False

    async def cache_channels(self, channels: List[Dict]):
        """
        Saves channels to a local JSON file for data efficiency.
        """
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(channels, f)

    def load_cached_channels(self) -> List[Dict]:
        """
        Loads channels from the local cache.
        """
        if os.path.exists(self.cache_file):
            with open(self.cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    async def close(self):
        await self.client.aclose()

# Global instance
iptv_service = IPTVService()
