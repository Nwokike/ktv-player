import logging

import anyio
import httpx

from core.constants import USER_AGENT
from core.url_validator import is_valid_play_url
from services.http_client import get_http_client
from services.m3u_parser import parse_m3u_text

logger = logging.getLogger(__name__)

# Hostile-host guard: a 50MB "playlist" must never be buffered on Android.
_MAX_PLAYLIST_BYTES = 8 * 1024 * 1024

_PLAYLIST_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)


class PlaylistFetchError(Exception):
    """A playlist fetch failed (network, status, size, or decode).

    Carries the URL + root cause so callers can distinguish FAILURE from a
    legitimately empty playlist (the old `return []` made them identical) and
    fall back to stale cache with an honest log line. Cancellation is NEVER
    wrapped in this — it propagates bare.
    """

    def __init__(self, url: str, cause: BaseException | str):
        super().__init__(f"Playlist fetch failed for {url}: {cause}")
        self.url = url
        self.cause = cause


class IPTVService:
    def get_client(self) -> httpx.AsyncClient:
        return get_http_client()

    async def _parse_m3u_from_url(self, url: str) -> list[dict]:
        # Validate before touching the network (empty/whitespace/non-http,
        # over-length, control chars, missing host, userinfo).
        cleaned = (url or "").strip() if isinstance(url, str) else ""
        if not is_valid_play_url(cleaned) or not cleaned.startswith(
            ("http://", "https://")
        ):
            raise PlaylistFetchError(url, f"unsupported playlist URL: {url!r}")
        try:
            client = self.get_client()
            # Streamed + capped: resp.text buffers the whole body first.
            buf = bytearray()
            async with client.stream(
                "GET",
                cleaned,
                headers={"User-Agent": USER_AGENT},
                timeout=_PLAYLIST_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(65536):
                    buf.extend(chunk)
                    if len(buf) > _MAX_PLAYLIST_BYTES:
                        raise PlaylistFetchError(
                            cleaned,
                            f"playlist exceeds {_MAX_PLAYLIST_BYTES} byte cap",
                        )
            text = bytes(buf).decode("utf-8-sig", errors="replace")
            parsed = await anyio.to_thread.run_sync(parse_m3u_text, text, "Custom")
            return parsed
        except PlaylistFetchError:
            raise
        except Exception as ex:
            # CancelledError is a BaseException, not Exception: it propagates
            # bare through this clause. Everything else (including non-HTTPError
            # httpx failures like InvalidURL/StreamError) becomes a typed
            # PlaylistFetchError per the contract.
            logger.warning("Failed to fetch playlist from %s: %s", cleaned, ex)
            raise PlaylistFetchError(cleaned, ex) from ex

    async def fetch_playlist(self, url: str) -> list[dict]:
        return await self._parse_m3u_from_url(url)


iptv_service = IPTVService()
