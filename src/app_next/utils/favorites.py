"""Favorites toggle utility for app_next components."""

import asyncio

from database.manager import db_manager


def toggle_favorite(url: str, state) -> None:
    """Fire-and-forget favorite toggle."""
    async def _do():
        try:
            if url in (state.favorites or []):
                await db_manager.remove_favorite(url)
                if url in state.favorites:
                    state.favorites.remove(url)
            else:
                await db_manager.add_favorite(url)
                state.favorites.append(url)
        except Exception:
            pass

    asyncio.create_task(_do())
