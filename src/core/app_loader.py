"""Channel loading and state restoration helpers for AppController."""

import logging

import flet as ft
from channels.provider import channel_provider
from core.constants import ERR_NETWORK
from core.state import state
from core.theme import AppColors
from database.manager import db_manager
from services.iptv_service import iptv_service

logger = logging.getLogger(__name__)


async def load_all_channels(page_obj, loading_lock):
    """Fetch and merge built-in, custom, and playlist channels into global state."""
    if loading_lock.locked():
        return

    async with loading_lock:
        from views.tabs.channel_groups import _invalidate_groups_cache

        _invalidate_groups_cache()

        state.is_loading = True
        page_obj.update()

        try:
            channels = await channel_provider.get_all_channels()

            # Merge custom channels
            custom_channels = await db_manager.get_custom_channels()
            for cc in custom_channels:
                cc["is_custom"] = True
                channels.append(cc)

            # Merge playlists
            playlists = await db_manager.get_playlists()
            for pl in playlists:
                if pl.get("is_active"):
                    try:
                        playlist_channels = await iptv_service.fetch_playlist(
                            pl["url"],
                        )
                        for pc in playlist_channels:
                            pc["is_custom"] = True
                        channels.extend(playlist_channels)
                    except Exception:
                        logger.exception(
                            "Failed to fetch playlist: %s",
                            pl.get("name"),
                        )

            state.set_channels(channels)
        except Exception:
            logger.exception("Failed to load channels")
            try:
                page_obj.snack_bar = ft.SnackBar(
                    ft.Text("Failed to load channels. Check your connection."),
                    bgcolor=AppColors.ERROR,
                )
                page_obj.snack_bar.open = True
            except Exception:
                pass
        finally:
            state.is_loading = False
            refresh = getattr(page_obj, "_dashboard_refresh", None)
            if refresh:
                refresh()
            page_obj.update()
