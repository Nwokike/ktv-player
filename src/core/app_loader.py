"""Channel loading and state restoration helpers for AppController."""

import logging

import flet as ft

from channels.provider import channel_provider
from core.state import state
from core.theme import AppColors
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
                merged.append(cc)
                if url:
                    seen_urls.add(url)

            # Merge playlists
            playlists = await db_manager.get_playlists()
            for pl in playlists:
                if pl.get("is_active"):
                    try:
                        playlist_channels = await iptv_service.fetch_playlist(
                            pl["url"],
                        )
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
                page_obj.show_dialog(
                    ft.SnackBar(
                        ft.Text("Failed to load channels. Check your connection."),
                        bgcolor=AppColors.ERROR,
                    )
                )
            except Exception:
                pass
