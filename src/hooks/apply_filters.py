"""apply_filters — pure filter function over the channel list.

This module has ZERO Flet imports so it is trivially testable. Used by
HomeScreen and other views. The filter dict contract:

    {
        "country": "all" | <name>,
        "category": "all" | <name>,
        "custom": "none" | "all" | "single" | <m3u_group>,
        "fav_only": False,
        "search": "",
    }
"""

from utils.channels import categories_of, country_of


def reconcile_filters(
    filters: dict,
    available_countries: dict,
    available_categories: dict,
    available_custom: dict | None = None,
) -> dict:
    """Reset selections whose folder no longer exists after a playlist swap.

    Pure and total: without it a saved country that vanished from the new
    source makes exact-match filtering return ZERO channels forever, with
    no error and no way back except manually re-picking a folder. Custom
    groups keep their sentinels ("none"/"all"/"single").
    """
    out = dict(filters)

    country = out.get("country", "all")
    if country != "all" and country not in available_countries:
        out["country"] = "all"

    category = out.get("category", "all")
    if category != "all" and category not in available_categories:
        out["category"] = "all"

    custom = out.get("custom", "none")
    custom_ok = {"none", "all", "single"}
    if (
        available_custom is not None
        and custom not in custom_ok
        and custom not in available_custom
    ):
        out["custom"] = "none"
    return out


def _default_filters(user_country: str = "") -> dict:
    if not user_country:
        country_val = "all"
    elif user_country == "Other":
        country_val = "Global"
    else:
        country_val = user_country
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
        elif custom_sel != "all":
            # Match against M3U group-title (supports multi-group like "Kids;Religious")
            groups = [g.strip() for g in c.get("group", "").split(";")]
            if custom_sel not in groups:
                return False
    else:
        # 4. Built-in Country & Category Filters (applies to built-in channels)
        country = filters.get("country", "all")
        if country != "all":
            if is_custom:
                return False
            if country_of(c) != country:
                return False

        category = filters.get("category", "all")
        if category != "all":
            if is_custom:
                return False
            # Membership, not "last segment": a premium-pack channel sits
            # in every tag it carries, and a full-group match still works.
            if category not in categories_of(c) and c.get("group") != category:
                return False

    return True


def apply_filters(
    channels: list[dict], filters: dict, favorites_set: set[str]
) -> list[dict]:
    """Return channels matching `filters`."""
    return [c for c in channels if _matches(c, filters, favorites_set)]
