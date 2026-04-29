import httpx
from m3u_parser import M3uParser
from typing import List, Dict

class ChannelProvider:
    def __init__(self):
        self.MASTER_PLAYLIST_URL = "https://raw.githubusercontent.com/Nwokike/IPTV/master/playlist.m3u8"

    def get_all_channels(self) -> List[Dict]:
        """Fetches and parses the M3U playlist directly from GitHub."""
        channels = []
        try:
            response = httpx.get(self.MASTER_PLAYLIST_URL, timeout=15.0, verify=False)
            response.raise_for_status()
            m3u_content = response.text
            parser = M3uParser(timeout=5)
            parser.parse_m3u_content(m3u_content)
            non_country_groups = ["movies", "news", "sports", "documentaries", "music", "kids", "comedy", "vod"]

            for stream in parser.get_list():
                category = stream.get("category", "Global")
                if isinstance(category, list) and len(category) > 0:
                    category = category[0]

                # Determine if this is a Country or a Category based on the group name
                is_country = not any(cat in category.lower() for cat in non_country_groups)

                channels.append({
                    "name": stream.get("name", "Unknown Channel"),
                    "url": stream.get("url", ""),
                    "logo": stream.get("logo", "/icon.png"),
                    "group": category,
                    # If it's a country, give it a truthy country_code so dashboard.py puts it in Tab 1
                    "country_code": "M3U" if is_country else "",
                    "is_custom": False
                })
                
        except Exception as e:
            print(f"Failed to fetch channels from GitHub: {e}")
            
        return channels

channel_provider = ChannelProvider()
