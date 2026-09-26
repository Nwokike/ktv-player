import asyncio
import contextlib
import logging
import os
import tempfile
import time

from channels.normalize import normalize_legacy, normalize_premium
from core.constants import premium_pack_url
from services.http_client import get_http_client
from services.m3u_parser import parse_m3u_text
from services.youtube_resolver import is_youtube_url

logger = logging.getLogger(__name__)

_cache_env = os.getenv("FLET_APP_STORAGE_CACHE")
_CACHE_DIR = (
    os.path.join(_cache_env, "data") if _cache_env else os.path.join("storage", "data")
)
_CACHE_FILE = os.path.join(_CACHE_DIR, "cached_playlist.m3u8")


def _cache_path(tier: str) -> str:
    """Free keeps the historical filename (no migration, no re-fetch);
    premium gets its own file so a pack fetch can never poison or leak
    into the free tier's cache (they share one mtime TTL each otherwise)."""
    if tier == "premium":
        return os.path.join(_CACHE_DIR, "cached_playlist.premium.m3u8")
    return _CACHE_FILE


def _current_tier() -> str:
    # Lazy import: provider loads early via settings/onboarding, before the
    # state singleton's own import chain is guaranteed settled.
    from core.state import state

    return "premium" if state.is_premium else "free"


def _write_cache(text: str, path: str | None = None) -> None:
    """Write playlist text to cache file atomically (tmp + rename).

    newline="" is load-bearing on Windows: text mode would translate
    every \\n to \\r\\n, turning the pack's own CRLF into \\r\\r\\n. Read
    back through universal newlines, that doubles every line break into a
    blank line, the parser sees an empty URL line, and the whole playlist
    parses to ZERO channels (Home then sits on the loading state forever).
    """
    target = path or _CACHE_FILE
    os.makedirs(_CACHE_DIR, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=_CACHE_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp_path, target)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _read_cache_file(path: str | None = None) -> str | None:
    target = path or _CACHE_FILE
    try:
        if os.path.exists(target):
            with open(target, encoding="utf-8") as f:
                return f.read()
    except OSError:
        pass
    return None


class ChannelProvider:
    def __init__(self):
        self.MASTER_PLAYLIST_URL = (
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
        )
        self.PLAYLIST_SOURCES = [
            "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8",
            "https://nwokike.github.io/IPTV/playlist.m3u8",
        ]
        self.CACHE_DURATION = 24 * 60 * 60
        self.STALE_DURATION = 48 * 60 * 60
        self._channels = []
        self._refresh_lock = None

    async def _get_refresh_lock(self):
        if self._refresh_lock is None:
            self._refresh_lock = asyncio.Lock()
        return self._refresh_lock

    def _parse(self, text: str, tier: str) -> list[dict]:
        channels = parse_m3u_text(text, default_group="General")
        normalize = normalize_premium if tier == "premium" else normalize_legacy
        return normalize(channels)

    async def _load_source(
        self, tier: str, sources: list[str], cache_path: str, force: bool
    ) -> list[dict]:
        """Load ONE playlist source: tier cache with TTL, else network.

        Stateless on purpose: composed tier lists live on the provider,
        never here. Returns [] on total failure instead of raising, so one
        broken source cannot take the whole grid down.
        """
        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)
            cached_text = None if force else _read_cache_file(cache_path)

            # A cache that parses to zero channels is poisoned (an error
            # page, truncated junk, or a legacy newline-corrupted file):
            # discard it and refetch instead of serving an empty grid on
            # every launch until the user finds the Refresh button.
            if cached_text and not self._parse(cached_text, tier):
                logger.warning(
                    "Playlist cache parsed to 0 channels; discarding %s", cache_path
                )
                cached_text = None
                with contextlib.suppress(OSError):
                    os.remove(cache_path)

            served: list[dict] = []
            if cached_text:
                file_age = time.time() - os.path.getmtime(cache_path)
                if file_age < self.CACHE_DURATION:
                    # Fresh cache — use it, no refresh needed.
                    logger.info(
                        "Using fresh playlist cache (age: %.1f hours)", file_age / 3600
                    )
                    served = self._parse(cached_text, tier)
                    logger.info("Loaded %d channels from playlist cache", len(served))
                    return served
                if file_age < self.STALE_DURATION:
                    # Stale but usable — serve it, then try a refresh below.
                    logger.info(
                        "Playlist cache is stale (age: %.1f hours); serving and refreshing in background",
                        file_age / 3600,
                    )
                    served = self._parse(cached_text, tier)

            client = get_http_client()
            fetched_text = None
            for url in sources:
                try:
                    logger.info("Fetching master playlist from %s", url)
                    response = await client.get(url, timeout=30.0)
                    response.raise_for_status()
                    fetched_text = response.text
                    if fetched_text and len(fetched_text) > 100:
                        break
                except Exception as ex:
                    logger.warning("Failed to fetch playlist %s: %s", url, ex)

            if fetched_text:
                fetched_channels = self._parse(fetched_text, tier)
                if fetched_channels:
                    await asyncio.to_thread(_write_cache, fetched_text, cache_path)
                    logger.info(
                        "Master playlist fetched successfully: %d channels parsed",
                        len(fetched_channels),
                    )
                    return fetched_channels
                # Never persist text that parses to nothing (an HTML error
                # page would poison the cache).
                logger.warning("Fetched playlist parsed to 0 channels; not caching")
            return served  # stale fallback, or [] when there is nothing
        except Exception:
            logger.exception("Error loading playlist source (%s)", tier)
            return []

    def _compose(
        self, tier: str, free_channels: list[dict], pack_channels: list[dict]
    ) -> list[dict]:
        """Premium = the pack PLUS the base playlist's YouTube entries.

        The iptv-org pack ships zero YouTube streams (verified against the
        live index), while the base playlist carries 133 YouTube live
        channels. Dropping the base on the swap took those with it for
        premium users. They cost nothing to keep: the player resolves any
        YouTube URL through youtube_resolver before playback, the pack has
        no YouTube entries to duplicate against, and keeping the original
        URLs means YouTube favorites survive the tier flip untouched.
        """
        if tier != "premium":
            return free_channels
        youtube = [c for c in free_channels if is_youtube_url(c.get("url", ""))]
        logger.info(
            "Premium channels composed: %d pack + %d YouTube = %d",
            len(pack_channels),
            len(youtube),
            len(pack_channels) + len(youtube),
        )
        return pack_channels + youtube

    def _compose_from_cache(self, tier: str) -> list[dict]:
        """Disk-only composition (no network) for get_countries."""
        free_text = _read_cache_file(_cache_path("free"))
        free_channels = self._parse(free_text, "free") if free_text else []
        if tier != "premium":
            return free_channels
        pack_text = _read_cache_file(_cache_path("premium"))
        pack_channels = self._parse(pack_text, "premium") if pack_text else []
        return self._compose(tier, free_channels, pack_channels)

    async def get_all_channels(self, force: bool = False) -> list[dict]:
        tier = _current_tier()
        if self._channels and not force:
            return list(self._channels)

        lock = await self._get_refresh_lock()
        if lock.locked():
            # Another caller is already fetching; serve what we have
            # (possibly nothing) instead of stacking a second download.
            await asyncio.sleep(0.5)
            return list(self._channels)

        async with lock:
            if self._channels and not force:
                return list(self._channels)
            free_channels = await self._load_source(
                tier="free",
                sources=self.PLAYLIST_SOURCES,
                cache_path=_cache_path("free"),
                force=force,
            )
            if tier == "premium":
                pack_channels = await self._load_source(
                    tier="premium",
                    sources=[premium_pack_url()],
                    cache_path=_cache_path("premium"),
                    force=force,
                )
                self._channels = self._compose(tier, free_channels, pack_channels)
            else:
                self._channels = free_channels

        return list(self._channels)

    def get_countries(self) -> list[dict]:
        tier = _current_tier()
        channels = self._channels
        if not channels:
            channels = self._compose_from_cache(tier)

        seen = set()
        countries = []
        for c in channels:
            if c.get("is_custom"):
                continue
            name = c.get("country", "")
            if name and name != "Global" and name not in seen:
                seen.add(name)
                countries.append({"name": name})
        countries.sort(key=lambda x: x["name"])
        return countries


channel_provider = ChannelProvider()
