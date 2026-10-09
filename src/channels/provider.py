import asyncio
import contextlib
import logging
import os
import tempfile
import time
from pathlib import Path

import anyio
import httpx

from channels.normalize import normalize_legacy, normalize_premium
from channels.sidecar import load_sidecar, sidecar_path, store_sidecar
from core.constants import USER_AGENT, premium_pack_url
from services.http_client import get_http_client
from services.m3u_parser import parse_m3u_text
from services.youtube_resolver import is_youtube_url

logger = logging.getLogger(__name__)

_PLAYLIST_TIMEOUT = httpx.Timeout(connect=5.0, read=20.0, write=10.0, pool=5.0)


def _cache_dir() -> str:
    """Resolve the playlist cache dir per call (not import time).

    Tests and late storage setup can change FLET_APP_STORAGE_CACHE after
    import; resolving lazily keeps them on the right directory.
    """
    cache_env = os.getenv("FLET_APP_STORAGE_CACHE")
    # Playlist caches are rebuildable, so they belong under the CACHE dir
    # (FLET_APP_STORAGE_CACHE) per the storage contract — including the
    # env-less fallback, which used to land in storage/data and mix
    # cache-class files with durable state.
    if cache_env:
        return os.path.join(cache_env, "data")
    return os.path.join("storage", "cache")


def _cache_file() -> str:
    return os.path.join(_cache_dir(), "cached_playlist.m3u8")


def _cache_path(tier: str) -> str:
    """Free keeps the historical filename (no migration, no re-fetch);
    premium gets its own file so a pack fetch can never poison or leak
    into the free tier's cache (they share one mtime TTL each otherwise)."""
    if tier == "premium":
        return os.path.join(_cache_dir(), "cached_playlist.premium.m3u8")
    return _cache_file()


def _current_tier() -> str:
    # Lazy import: provider loads early via settings/onboarding, before the
    # state singleton's own import chain is guaranteed settled.
    from core.state import state

    return "premium" if state.is_premium else "free"


def _cache_dir_path() -> Path:
    return Path(_cache_dir())


def _write_cache(text: str, path: str | None = None) -> None:
    """Write playlist text to cache file atomically (tmp + rename).

    newline="" is load-bearing on Windows: text mode would translate
    every \\n to \\r\\n, turning the pack's own CRLF into \\r\\r\\n. Read
    back through universal newlines, that doubles every line break into a
    blank line, the parser sees an empty URL line, and the whole playlist
    parses to ZERO channels (Home then sits on the loading state forever).
    """
    target = path or _cache_file()
    cache_dir = _cache_dir()
    os.makedirs(cache_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=cache_dir, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp_path, target)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def _read_cache_file(path: str | None = None) -> str | None:
    target = path or _cache_file()
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
        self._channels: list[dict] = []
        self._tier: str | None = None
        # Eager lock: creating asyncio.Lock() in __init__ is safe on 3.10+
        # (no loop binding at construction) and avoids the lazy-creation race
        # where two coroutines each build their own lock.
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        """Drop in-memory channels (e.g. on tier change or explicit refresh).

        Encapsulates what used to be an external `provider._channels = []`
        poke from app_loader, so invalidation stays inside the lock owner.
        Must be called with the lock held or from sync code that owns it.
        """
        self._channels = []

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
        served: list[dict] = []
        try:
            os.makedirs(_cache_dir(), exist_ok=True)
            # force=True skips the FRESH fast-path below but keeps the disk
            # text as an offline fallback: a manual Refresh with no network
            # must serve stale cache, not wipe the grid.
            cached_text = _read_cache_file(cache_path)

            # Sidecar first: the parsed result, validated against the raw
            # file's mtime+size. A hit skips the regex parse entirely (the
            # cold-start win); a miss falls through to a normal parse.
            cached_channels: list[dict] = []
            sidecar_channels: list[dict] | None = None
            if cached_text:
                sidecar_channels = load_sidecar(cache_path)
                if sidecar_channels is not None:
                    cached_channels = sidecar_channels
                else:
                    cached_channels = await anyio.to_thread.run_sync(
                        self._parse, cached_text, tier
                    )

            # A cache that parses to zero channels is poisoned (an error
            # page, truncated junk, or a legacy newline-corrupted file):
            # discard it and refetch instead of serving an empty grid on
            # every launch until the user finds the Refresh button.
            # Parse once and reuse for the poison check and the serve path.
            if cached_text and not cached_channels:
                logger.warning(
                    "Playlist cache parsed to 0 channels; discarding %s", cache_path
                )
                cached_text = None
                with contextlib.suppress(OSError):
                    os.remove(cache_path)
                # Remove the orphan sidecar too: it stats the missing raw
                # file next load and returns None, but leaving it behind
                # strands trash on disk for every poisoned cache.
                with contextlib.suppress(OSError):
                    os.remove(sidecar_path(cache_path))

            if cached_text:
                try:
                    file_age = time.time() - os.path.getmtime(cache_path)
                except OSError:
                    # Raced with a concurrent refresh or external cleaner that
                    # deleted the file after we read it: treat as infinitely
                    # stale and fall through to network, keeping served as
                    # the in-memory fallback.
                    file_age = float("inf")
                if file_age < self.CACHE_DURATION and not force:
                    # Fresh cache — use it, no refresh needed. First Phase 8
                    # launch has no sidecar yet: store it so the NEXT launch
                    # skips the parse.
                    if sidecar_channels is None and cached_channels:
                        await anyio.to_thread.run_sync(
                            store_sidecar, cache_path, cached_channels
                        )
                    logger.info(
                        "Using fresh playlist cache (age: %.1f hours)", file_age / 3600
                    )
                    served = cached_channels
                    logger.info("Loaded %d channels from playlist cache", len(served))
                    return served
                if file_age < self.STALE_DURATION:
                    # Stale but usable — serve it, then try a refresh below.
                    # NOTE: comment lies fixed — this blocks on the refresh;
                    # the stale list is the fallback if the fetch fails.
                    logger.info(
                        "Playlist cache is stale (age: %.1f hours); serving stale "
                        "while attempting refresh",
                        file_age / 3600,
                    )
                    served = cached_channels

            client = get_http_client()
            fetched_text = None
            for url in sources:
                try:
                    logger.info("Fetching master playlist from %s", url)
                    # Streamed + capped (not resp.text): the premium pack is
                    # multi-MB and a hostile host must not OOM the app. Cap is
                    # generous (16MB) — trusted first-party indexes, unlike the
                    # 8MB cap on user-supplied custom URLs in iptv_service.
                    buf = bytearray()
                    async with client.stream(
                        "GET",
                        url,
                        timeout=_PLAYLIST_TIMEOUT,
                        headers={"User-Agent": USER_AGENT},
                    ) as response:
                        response.raise_for_status()
                        async for chunk in response.aiter_bytes(65536):
                            buf.extend(chunk)
                            if len(buf) > 16 * 1024 * 1024:
                                raise ValueError("playlist exceeds 16MB cap")
                    fetched_text = bytes(buf).decode("utf-8-sig", errors="replace")
                    if fetched_text and len(fetched_text) > 100:
                        break
                except asyncio.CancelledError:
                    raise
                except Exception as ex:
                    logger.warning("Failed to fetch playlist %s: %s", url, ex)

            if fetched_text:
                fetched_channels = await anyio.to_thread.run_sync(
                    self._parse, fetched_text, tier
                )
                if fetched_channels:
                    await anyio.to_thread.run_sync(
                        _write_cache, fetched_text, cache_path
                    )
                    # Refresh the sidecar to match the new raw file so the
                    # next launch skips the parse.
                    await anyio.to_thread.run_sync(
                        store_sidecar, cache_path, fetched_channels
                    )
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
            # Never discard already-served stale data on a late failure
            # (getmtime race, cache write error, ...).
            return served

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
        youtube = [c for c in free_channels if is_youtube_url(c.get("url") or "")]
        logger.info(
            "Premium channels composed: %d pack + %d YouTube = %d",
            len(pack_channels),
            len(youtube),
            len(pack_channels) + len(youtube),
        )
        composed = pack_channels + youtube
        # One upstream change (pack gaining YouTube entries) would duplicate
        # rows: dedup by URL, first wins.
        seen: set[str] = set()
        deduped: list[dict] = []
        for c in composed:
            url = c.get("url") or ""
            if url and url in seen:
                continue
            seen.add(url)
            deduped.append(c)
        return deduped

    def _compose_from_cache(self, tier: str) -> list[dict]:
        """Disk-only composition (no network) for get_countries."""
        free_path = _cache_path("free")
        free_text = _read_cache_file(free_path)
        # Sync path: sidecar hit avoids the parse entirely; the msgpack
        # unpack is single-digit ms versus the multi-second regex parse.
        free_channels = (
            (load_sidecar(free_path) or self._parse(free_text, "free"))
            if free_text
            else []
        )
        if tier != "premium":
            return free_channels
        pack_path = _cache_path("premium")
        pack_text = _read_cache_file(pack_path)
        pack_channels = (
            (load_sidecar(pack_path) or self._parse(pack_text, "premium"))
            if pack_text
            else []
        )
        return self._compose(tier, free_channels, pack_channels)

    async def get_all_channels(self, force: bool = False) -> list[dict]:
        tier = _current_tier()
        # Every caller waits on the same lock: a concurrent refresh blocks
        # here instead of getting a possibly-empty snapshot after 0.5s.
        async with self._lock:
            if tier != self._tier:
                # Tier flip (free→premium unlock or expiry): the in-memory
                # list belongs to the other tier. Drop it so we serve the
                # right list below instead of the stale one.
                self._channels = []
                self._tier = tier
            if self._channels and not force:
                return list(self._channels)
            free_channels, pack_channels = await asyncio.gather(
                self._load_source(
                    tier="free",
                    sources=self.PLAYLIST_SOURCES,
                    cache_path=_cache_path("free"),
                    force=force,
                ),
                self._load_source(
                    tier="premium",
                    sources=[premium_pack_url()],
                    cache_path=_cache_path("premium"),
                    force=force,
                )
                if tier == "premium"
                else asyncio.sleep(0, result=[]),
            )
            if tier == "premium":
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
