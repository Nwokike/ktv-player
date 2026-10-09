"""Channel loading and state restoration helpers for AppController."""

import asyncio
import logging
from pathlib import PurePosixPath
from urllib.parse import urlparse

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
        # Prefer same-group matches before bare-name matches: duplicate names
        # across groups/countries otherwise remap deterministically but possibly
        # to the wrong regional variant.
        url_by_group_name: dict[tuple[str, str], str] = {}
        url_by_name: dict[str, str] = {}
        for c in channels:
            name = c.get("name", "")
            url = c.get("url", "")
            if name and url:
                url_by_group_name.setdefault((c.get("group", ""), name), url)
                if name not in url_by_name:
                    url_by_name[name] = url

        remapped = 0
        orphaned = 0
        # Favorite URLs (not live channel URLs): two stored entries collapsing
        # onto one live URL must dedup, but remapping onto a live-but-unfavorited
        # URL is the normal path and must go through remap_favorite_url.
        fav_urls = {f.get("url", "") for f in stored if isinstance(f, dict)}
        for fav in stored:
            if not isinstance(fav, dict):
                orphaned += 1
                continue
            old = fav.get("url", "")
            if not old or old in live_urls:
                continue
            new = url_by_group_name.get(
                (fav.get("group", ""), fav.get("name", "")),
                url_by_name.get(fav.get("name", "")),
            )
            if not new:
                orphaned += 1
                continue
            if new in fav_urls and new != old:
                # Another stored favorite already uses the new URL: drop the
                # stale entry instead of creating a duplicate favorite.
                if await db_manager.remove_favorite(old):
                    remapped += 1
                fav_urls.discard(old)
                continue
            if await db_manager.remap_favorite_url(old, new):
                remapped += 1
                fav_urls.discard(old)
                fav_urls.add(new)
            else:
                orphaned += 1

        if remapped:
            state.favorites = sorted(await db_manager.get_favorite_urls())
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


async def load_all_channels(page_obj=None, loading_lock=None, force: bool = False):
    """Fetch and merge built-in, custom, and playlist channels into global state.

    page_obj is accepted for API compatibility and intentionally unused:
    state is @ft.observable so no manual page.update() is needed.
    """
    if loading_lock is None:
        loading_lock = asyncio.Lock()
    async with loading_lock:
        try:
            # No in-memory clear here: force=True already bypasses the cache
            # short-circuit inside the provider, and clearing first would serve
            # [] to concurrent readers mid-fetch (and wipe the grid offline).
            built_in = await channel_provider.get_all_channels(force=force)

            # Build merged list from scratch with URL-based deduplication.
            # Every element is a shallow copy: built_in/custom/playlist dicts
            # are owned by the provider/DB, and mutating them in place (e.g.
            # setting is_custom) would leak flags into durable storage.
            merged: list[dict] = []
            seen_urls: set[str] = set()

            for ch in built_in:
                if not isinstance(ch, dict):
                    continue
                merged.append(dict(ch))
                url = ch.get("url", "")
                if url:
                    seen_urls.add(url)

            # Merge custom channels
            custom_channels = await db_manager.get_custom_channels()
            for cc in custom_channels:
                if not isinstance(cc, dict):
                    continue
                url = cc.get("url", "")
                if url and url in seen_urls:
                    continue
                entry = dict(cc)
                entry["is_custom"] = True
                entry["is_single_custom"] = True
                merged.append(entry)
                if url:
                    seen_urls.add(url)

            # Merge playlists — M3U group-title is preserved as-is.
            # Fetches run concurrently: sequentially they held the loading
            # lock for N x 20s (per-playlist httpx timeout) on slow hosts.
            # Overall wait_for bounds the whole fan-out so one slow host plus
            # a slow DNS cannot hold the lock indefinitely.
            playlists = await db_manager.get_playlists()
            active_playlists = [
                pl
                for pl in playlists
                if isinstance(pl, dict) and pl.get("is_active") and pl.get("url")
            ]
            skipped = len(playlists) - len(active_playlists)
            if skipped:
                logger.warning("Skipping %d playlist rows with missing URL", skipped)
            if active_playlists:
                from services.iptv_service import PlaylistFetchError

                async def _safe_fetch(pl: dict) -> list[dict]:
                    # One bad custom playlist must not abort the whole load:
                    # isolate failures per playlist, keep stale/built-in UX.
                    try:
                        return await iptv_service.fetch_playlist(pl["url"])
                    except PlaylistFetchError as ex:
                        logger.warning("Playlist %s failed: %s", pl.get("name"), ex)
                        return []
                    except asyncio.CancelledError:
                        raise
                    except Exception as ex:
                        logger.warning("Playlist %s failed: %s", pl.get("name"), ex)
                        return []

                try:
                    fetched_lists = await asyncio.wait_for(
                        asyncio.gather(
                            *(_safe_fetch(pl) for pl in active_playlists),
                        ),
                        timeout=60.0,
                    )
                except TimeoutError:
                    logger.warning("Playlist fan-out exceeded 60s; using built-in")
                    fetched_lists = [[] for _ in active_playlists]
                for pl, playlist_channels in zip(
                    active_playlists, fetched_lists, strict=True
                ):
                    try:
                        # Auto-detect flat playlists: if ALL channels got
                        # group="Custom" (no group-title in M3U), derive a
                        # group name from the URL domain so they appear
                        # as a named entry in the Custom dropdown.
                        if playlist_channels and all(
                            c.get("group", "Custom") == "Custom"
                            for c in playlist_channels
                        ):
                            parsed = urlparse(pl.get("url") or "")
                            host = parsed.hostname or ""
                            stem = PurePosixPath(parsed.path).stem
                            name = (
                                f"{host} - {stem}"
                                if host and stem
                                else host or stem or "Playlist"
                            )
                            for c in playlist_channels:
                                if isinstance(c, dict):
                                    c["group"] = name

                        for pc in playlist_channels:
                            if not isinstance(pc, dict):
                                continue
                            pc_url = pc.get("url", "")
                            if pc_url and pc_url in seen_urls:
                                continue
                            entry = dict(pc)
                            entry["is_custom"] = True
                            merged.append(entry)
                            if pc_url:
                                seen_urls.add(pc_url)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        logger.exception(
                            "Failed to merge playlist: %s",
                            pl.get("name"),
                        )

            if not merged:
                # Empty success must not wipe a good grid (offline refresh with
                # dead caches, all playlists failing): keep stale state.
                logger.warning("Channel load produced no channels; keeping stale")
                try:
                    from utils.notifications import notify_error

                    notify_error("Failed to load channels. Check your connection.")
                except Exception:
                    pass
                return
            state.set_channels(merged)
            await _reconcile_favorites(merged)
        except asyncio.CancelledError:
            raise
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
