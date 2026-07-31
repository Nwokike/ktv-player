"""Favorites toggle utility."""

import asyncio
import logging

from database.manager import db_manager

logger = logging.getLogger(__name__)

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
            logger.exception("Failed to toggle favorite for %s", url)
        finally:
            _in_flight.discard(url)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_do())
    except RuntimeError:
        pass
