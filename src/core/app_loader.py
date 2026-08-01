"""Channel loading and state restoration helpers for AppController."""

import logging

from channels.provider import channel_provider
from core.state import state
from database.manager import db_manager
from services.iptv_service import iptv_service

logger = logging.getLogger(__name__)


async def load_all_channels(page_obj, loading_lock):
    """Fetch and merge built-in, custom, and playlist channels into global state."""
    async with loading_lock:
        try:
            built_in = await channel_provider.get_all_channels()

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

            # Merge playlists — M3U group-title is preserved as-is
            playlists = await db_manager.get_playlists()
            for pl in playlists:
                if pl.get("is_active"):
                    try:
                        playlist_channels = await iptv_service.fetch_playlist(
                            pl["url"],
                        )
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
                            "Failed to fetch playlist: %s",
                            pl.get("name"),
                        )

            state.set_channels(merged)
        except Exception:
            logger.exception("Failed to load channels")
            try:
                from utils.notifications import notify_error

                notify_error("Failed to load channels. Check your connection.")
            except Exception:
                pass
