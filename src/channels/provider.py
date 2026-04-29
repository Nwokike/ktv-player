import os
import time
import httpx
import tempfile
from m3u_parser import M3uParser
from typing import List, Dict

class ChannelProvider:
    def __init__(self):
        self.MASTER_PLAYLIST_URL = "https://raw.githubusercontent.com/Nwokike/IPTV/master/playlist.m3u8"
        # Store the file safely in the device's temporary cache directory
        self.CACHE_FILE = os.path.join(tempfile.gettempdir(), "cached_playlist.m3u8")
        self.CACHE_DURATION = 24 * 60 * 60  # 24 hours in seconds

    def get_all_channels(self) -> List[Dict]:
        """Fetches the M3U playlist, caching it locally for 24 hours for instant loading."""
        channels = []
        try:
            # 1. Smart Caching Logic
            should_download = True
            if os.path.exists(self.CACHE_FILE):
                file_age = time.time() - os.path.getmtime(self.CACHE_FILE)
                if file_age < self.CACHE_DURATION:
                    should_download = False
            
            if should_download:
                print("Downloading fresh playlist from GitHub...")
                # Download and save the text locally
                response = httpx.get(self.MASTER_PLAYLIST_URL, timeout=15.0, verify=False, follow_redirects=True)
                response.raise_for_status()
                with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(response.text)
            else:
                print("Using lightning-fast local cache...")

            # 2. Parse from the local cached file
            parser = M3uParser(timeout=15)
            parser.parse_m3u(self.CACHE_FILE)
            
            # 3. Format the data to perfectly match your UI structure
            non_country_groups = ["movies", "news", "sports", "documentaries", "music", "kids", "comedy", "vod"]

            for stream in parser.get_list():
                category = stream.get("category", "Global")
                if isinstance(category, list) and len(category) > 0:
                    category = category[0]

                is_country = not any(cat in category.lower() for cat in non_country_groups)

                channels.append({
                    "name": stream.get("name", "Unknown Channel"),
                    "url": stream.get("url", ""),
                    "logo": stream.get("logo", "/icon.png"),
                    "group": category,
                    "country_code": "M3U" if is_country else "",
                    "is_custom": False
                })
                
        except Exception as e:
            print(f"Failed to fetch or parse channels: {e}")
            
        return channels

# Shared instance
channel_provider = ChannelProvider()
