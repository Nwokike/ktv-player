"""Favorites toggle utility for app_next components."""

import asyncio

from database.manager import db_manager

# Guards against rapid-fire toggles on the same URL.
_in_flight: set[str] = set()


def toggle_favorite(url: str, state) -> None:
    """Fire-and-forget favorite toggle."""

    async def _do():
        if url in _in_flight:
            return
        _in_flight.add(url)
        try:
            current = list(state.favorites or [])
            if url in current:
                await db_manager.remove_favorite(url)
                state.favorites = [u for u in current if u != url]
            else:
                await db_manager.add_favorite(url)
                state.favorites = current + [url]
        except Exception:
            pass
        finally:
            _in_flight.discard(url)

    asyncio.create_task(_do())
