"""Favorites toggle utility."""

import asyncio
import logging

from database.manager import db_manager

logger = logging.getLogger(__name__)

_in_flight: set[str] = set()


def _normalize_url(url: object) -> str:
    if not isinstance(url, str):
        return ""
    return url.strip()


async def toggle_favorite_async(url: str, state, db=None) -> bool:
    """Toggle one favorite; returns the new is-favorite state.

    Re-reads state after the DB write and applies an idempotent add/remove
    (no snapshot overwrite), so concurrent toggles cannot clobber each other.
    Raises on DB failure so callers can surface it (no silent divergence).
    """
    manager = db if db is not None else db_manager
    url = _normalize_url(url)
    if not url:
        raise ValueError(f"Invalid favorite url: {url!r}")
    favs = getattr(state, "favorites", None) or []
    is_fav = url in favs
    if is_fav:
        await manager.remove_favorite(url)
    else:
        await manager.add_favorite(url)
    # Re-read after the await: another toggle may have landed in between.
    # Apply idempotently instead of overwriting from a stale snapshot.
    current = list(getattr(state, "favorites", None) or [])
    if is_fav:
        state.favorites = [u for u in current if u != url]
    elif url not in current:
        state.favorites = [*current, url]
    return not is_fav


def toggle_favorite(url: str, state, db=None) -> asyncio.Task | None:
    """Fire-and-forget favorite toggle. Returns the task, or None if deduped.

    The in-flight guard is synchronous (checked before scheduling), so rapid
    double-taps actually debounce. No running loop → logs and re-raises
    instead of silently dropping the toggle.
    """
    norm = _normalize_url(url)
    if not norm:
        logger.warning("Ignoring invalid favorite url: %r", url)
        return None
    if norm in _in_flight:
        return None
    _in_flight.add(norm)

    async def _do():
        try:
            await toggle_favorite_async(norm, state, db)
        except Exception:
            logger.exception("Failed to toggle favorite for %s", norm)
        finally:
            _in_flight.discard(norm)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        _in_flight.discard(norm)
        logger.warning("No running loop; favorite toggle dropped for %s", norm)
        raise
    return loop.create_task(_do())
