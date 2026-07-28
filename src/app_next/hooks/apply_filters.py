"""apply_filters — pure filter function over the channel list.

This module has ZERO Flet imports so it is trivially testable. Used by
HomeScreen (M2) and SearchScreen (M3). The filter dict contract:

    {"country": "all" | <name>, "category": "all" | <name>,
     "fav_only": False, "source": "all" | "built-in" | "custom"}

Channel fields used:
    c["url"]               identity key (required)
    c["name"]              display name (optional, defaults "")
    c["group"]             category; ";-delimited, segment 0 = country
    c["is_custom"]         True for user-added (defaults False if missing)
    c["country_code"]      "M3U" / "" — only used for sorting/grouping priority

Returns:
    list[dict]: filtered channels, capped at MAX_SEARCH_RESULTS (50).
"""

from core.constants import MAX_SEARCH_RESULTS


def _default_filters() -> dict:
    return {
        "country": "all",
        "category": "all",
        "fav_only": False,
        "source": "all",
    }


def _matches(c: dict, filters: dict, favorites_set: set[str]) -> bool:
    country = filters.get("country", "all")
    if country != "all":
        group_segments = c.get("group", "General").split(";")
        channel_country = group_segments[0].strip() if group_segments else ""
        if channel_country != country:
            return False

    category = filters.get("category", "all")
    if category != "all" and c.get("group", "General") != category:
        return False

    if filters.get("fav_only", False) and c.get("url", "") not in favorites_set:
        return False

    source = filters.get("source", "all")
    if source == "built-in" and c.get("is_custom", False):
        return False

    if source == "custom":
        return c.get("is_custom", False)

    return True


def apply_filters(
    channels: list[dict], filters: dict, favorites_set: set[str]
) -> list[dict]:
    """Return channels matching `filters`, capped at MAX_SEARCH_RESULTS."""
    return [c for c in channels if _matches(c, filters, favorites_set)][
        :MAX_SEARCH_RESULTS
    ]
