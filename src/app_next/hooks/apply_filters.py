"""apply_filters — pure filter function over the channel list.

This module has ZERO Flet imports so it is trivially testable. Used by
HomeScreen and other views. The filter dict contract:

    {
        "country": "all" | <name>,
        "category": "all" | <name>,
        "custom": "none" | "all" | "single" | <playlist_name>,
        "fav_only": False,
        "search": "",
    }
"""

from core.constants import MAX_SEARCH_RESULTS


def _default_filters(user_country: str = "all") -> dict:
    country_val = "all" if not user_country or user_country == "Other" else user_country
    return {
        "country": country_val,
        "category": "all",
        "custom": "none",
        "fav_only": False,
        "search": "",
    }


def _matches(c: dict, filters: dict, favorites_set: set[str]) -> bool:
    # 1. Search Query Filter
    search_q = filters.get("search", "").strip().lower()
    if search_q:
        c_name = c.get("name", "").lower()
        c_url = c.get("url", "").lower()
        if search_q not in c_name and search_q not in c_url:
            return False

    # 2. Favorites Only Toggle
    if filters.get("fav_only", False) and c.get("url", "") not in favorites_set:
        return False

    is_custom = c.get("is_custom", False)

    # 3. Custom Filter Scope
    custom_sel = filters.get("custom", "none")
    if custom_sel != "none":
        if not is_custom:
            return False
        if custom_sel == "single":
            if not c.get("is_single_custom", False):
                return False
        elif custom_sel != "all" and c.get("playlist_name") != custom_sel:
            return False
    else:
        # 4. Built-in Country & Category Filters (applies to built-in channels)
        country = filters.get("country", "all")
        if country != "all":
            if is_custom:
                return False
            parts = [p.strip() for p in c.get("group", "General").split(";")]
            channel_country = parts[0] if c.get("country_code") else "Global"
            if channel_country != country:
                return False

        category = filters.get("category", "all")
        if category != "all":
            if is_custom:
                return False
            parts = [p.strip() for p in c.get("group", "General").split(";")]
            channel_category = (
                parts[-1]
                if len(parts) > 1
                else (parts[0] if not c.get("country_code") else "General")
            )
            if channel_category != category and c.get("group") != category:
                return False

    return True


def apply_filters(
    channels: list[dict], filters: dict, favorites_set: set[str]
) -> list[dict]:
    """Return channels matching `filters`, capped at MAX_SEARCH_RESULTS."""
    return [c for c in channels if _matches(c, filters, favorites_set)][
        :MAX_SEARCH_RESULTS
    ]
