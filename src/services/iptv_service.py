import logging

import httpx

from core.constants import USER_AGENT
from services.http_client import get_http_client
from services.m3u_parser import parse_m3u_text

logger = logging.getLogger(__name__)


class IPTVService:
    def get_client(self) -> httpx.AsyncClient:
        return get_http_client()

    async def _parse_m3u_from_url(self, url: str) -> list[dict]:
        try:
            client = self.get_client()
            headers = {"User-Agent": USER_AGENT}
            playlist_timeout = httpx.Timeout(20.0, connect=5.0, read=15.0)
            resp = await client.get(url, headers=headers, timeout=playlist_timeout)
            resp.raise_for_status()
            return parse_m3u_text(resp.text, default_group="Custom")
        except Exception as ex:
            # Never silent: a dead host must show up in logs, not as a
            # mysteriously empty channel list.
            logger.warning("Failed to fetch playlist from %s: %s", url, ex)
            return []

    async def fetch_playlist(self, url: str) -> list[dict]:
        return await self._parse_m3u_from_url(url)


iptv_service = IPTVService()
