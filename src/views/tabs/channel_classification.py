"""Channel group classification and cache management."""

import logging

from core.constants import MAX_SEARCH_RESULTS
from core.state import state

logger = logging.getLogger(__name__)

# Module-level groups cache
_groups_cache: dict = {"countries": {}, "categories": {}, "custom": {}, "hash": None}


def _invalidate_groups_cache():
    _groups_cache["countries"] = {}
    _groups_cache["categories"] = {}
    _groups_cache["custom"] = {}
    _groups_cache["hash"] = None


def classify_channel(channel: dict, tab_index: int) -> str | None:
    """Classify a single channel into its display group for the given tab."""
    is_custom = channel.get("is_custom", False)
    if tab_index == 2 and not is_custom:
        return None
    if tab_index in (0, 1) and is_custom:
        return None

    original_group = channel.get("group", "General")
    parts = [p.strip() for p in original_group.split(";")]

    if tab_index == 0:  # Countries
        return parts[0] if channel.get("country_code") else "Global"
    elif tab_index == 1:  # Categories
        group = (
            parts[-1]
            if len(parts) > 1
            else (parts[0] if not channel.get("country_code") else "General")
        )
        return None if group.lower() == "general" else group
    else:  # Custom
        return original_group


def _build_groups(channels: list[dict], tab_index: int) -> dict[str, list[dict]]:
    """Build groups dict, using cache when channels haven't changed."""
    cache_keys = {0: "countries", 1: "categories", 2: "custom"}
    cache_key = cache_keys.get(tab_index, "custom")

    if _groups_cache["hash"] == state.channels_hash and _groups_cache[cache_key]:
        return _groups_cache[cache_key]

    groups: dict[str, list[dict]] = {}
    for c in channels:
        display_group = classify_channel(c, tab_index)
        if display_group is None:
            continue
        if display_group not in groups:
            groups[display_group] = []
        groups[display_group].append(c)

    _groups_cache[cache_key] = groups
    _groups_cache["hash"] = state.channels_hash
    return groups


def _search_channels(
    channels: list[dict],
    query: str,
    tab_index: int,
) -> dict[str, list[dict]]:
    """Filter channels by search query using classify_channel logic."""
    groups: dict[str, list[dict]] = {}
    count = 0
    for c in channels:
        display_group = classify_channel(c, tab_index)
        if display_group is None:
            continue

        name_match = query in c.get("name", "").lower()
        if not name_match and query not in display_group.lower():
            continue

        count += 1
        if count > MAX_SEARCH_RESULTS:
            break

        if display_group not in groups:
            groups[display_group] = []
        groups[display_group].append(c)
    return groups
