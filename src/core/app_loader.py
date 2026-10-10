"""Channel loading and state restoration helpers for AppController."""

import asyncio
import logging

from channels.provider import channel_provider
from core.state import state
from database.manager import db_manager
from services.iptv_service import iptv_service

logger = logging.getLogger(__name__)


async def _reconcile_favorites(channels: list[dict]) -> None:
    """Re-key saved favorites after a playlist swap (URL-keyed storage).

    Best effort by exact channel name: the premium pack serves different
    stream URLs, so a star would otherwise silently vanish from the grid.
    Unmatched favorites are never deleted; the user is only told when
    something actually moved (a routine playlist refresh must not nag).
    """
    try:
        stored = await db_manager.get_favorites()
        if not stored:
            return
        live_urls = {c.get("url", "") for c in channels if c.get("url")}
        url_by_name: dict[str, str] = {}
        for c in channels:
            name = c.get("name", "")
            if name and c.get("url") and name not in url_by_name:
                url_by_name[name] = c["url"]

        remapped = 0
        orphaned = 0
        for fav in stored:
            old = fav.get("url", "")
            if not old or old in live_urls:
                continue
            new = url_by_name.get(fav.get("name", ""))
            if new and await db_manager.remap_favorite_url(old, new):
                remapped += 1
            else:
                orphaned += 1

        if remapped:
            state.favorites = list(await db_manager.get_favorite_urls())
            from utils.notifications import notify

            if orphaned:
                notify(
                    f"Updated {remapped} saved channels; "
                    f"{orphaned} are not in the new list."
                )
            else:
                notify(f"Updated {remapped} saved channels for the new list.")
        elif orphaned:
            logger.info("%d saved channels are not in the current playlist", orphaned)
    except Exception:
        logger.debug("Favorite re-key failed", exc_info=True)


async def load_all_channels(page_obj, loading_lock, force: bool = False):
    """Fetch and merge built-in, custom, and playlist channels into global state."""
    async with loading_lock:
        try:
            if force:
                channel_provider._channels = []
            built_in = await channel_provider.get_all_channels(force=force)

            # Build merged list from scratch with URL-based deduplication
            merged: list[dict] = []
            seen_urls: set[str] = set()

            for ch in built_in:
                merged.append(ch)
                url = ch.get("url", "")
                if url:
                    seen_urls.add(url)

            # Merge custom channels
            custom_channels = await db_manager.get_custom_channels()
            for cc in custom_channels:
                url = cc.get("url", "")
                if url and url in seen_urls:
                    continue
                cc["is_custom"] = True
                cc["is_single_custom"] = True
                merged.append(cc)
                if url:
                    seen_urls.add(url)

            # Merge playlists — M3U group-title is preserved as-is.
            # Fetches run concurrently: sequentially they held the loading
            # lock for N × 20s (per-playlist httpx timeout) on slow hosts.
            playlists = await db_manager.get_playlists()
            active_playlists = [pl for pl in playlists if pl.get("is_active")]
            if active_playlists:
                fetched_lists = await asyncio.gather(
                    *(
                        iptv_service.fetch_playlist(pl["url"])
                        for pl in active_playlists
                    ),
                    return_exceptions=True,
                )
                for pl, playlist_channels in zip(active_playlists, fetched_lists):
                    try:
                        if isinstance(playlist_channels, BaseException):
                            logger.warning(
                                "Failed to fetch playlist %s: %s",
                                pl.get("name"),
                                playlist_channels,
                            )
                            continue
                        # Auto-detect flat playlists: if ALL channels got
                        # group="Custom" (no group-title in M3U), derive a
                        # group name from the URL domain so they appear
                        # as a named entry in the Custom dropdown.
                        if playlist_channels and all(
                            c.get("group", "Custom") == "Custom"
                            for c in playlist_channels
                        ):
                            from pathlib import PurePosixPath
                            from urllib.parse import urlparse

                            parsed = urlparse(pl["url"])
                            host = parsed.hostname or ""
                            stem = PurePosixPath(parsed.path).stem
                            name = (
                                f"{host} — {stem}"
                                if host and stem
                                else host or stem or "Playlist"
                            )
                            for c in playlist_channels:
                                c["group"] = name

                        for pc in playlist_channels:
                            pc_url = pc.get("url", "")
                            if pc_url and pc_url in seen_urls:
                                continue
                            pc["is_custom"] = True
                            merged.append(pc)
                            if pc_url:
                                seen_urls.add(pc_url)
                    except Exception:
                        logger.exception(
                            "Failed to merge playlist: %s",
                            pl.get("name"),
                        )

            state.set_channels(merged)
            await _reconcile_favorites(merged)
        except RuntimeError as e:
            if "destroyed session" in str(e):
                logger.debug("Session destroyed during channel load — safe to ignore")
            else:
                logger.exception("Failed to load channels")
        except Exception:
            logger.exception("Failed to load channels")
            try:
                from utils.notifications import notify_error

                notify_error("Failed to load channels. Check your connection.")
            except Exception:
                pass
