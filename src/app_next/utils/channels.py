"""Channel utility functions for app_next components."""


def extract_countries(channels: list[dict]) -> list[str]:
    """Derive sorted country list from channel data. Returns strings."""
    seen = set()
    result = []
    for c in channels:
        group = c.get("group", "General")
        country = group.split(";")[0].strip()
        if country and country not in seen and c.get("country_code"):
            seen.add(country)
            result.append(country)
    return sorted(result)


def extract_country_dicts(channels: list[dict]) -> list[dict]:
    """Derive sorted country list from channel data. Returns dicts with 'name' key."""
    seen = set()
    result = []
    for c in channels:
        group = c.get("group", "General")
        country = group.split(";")[0].strip()
        if country and country not in seen and c.get("country_code"):
            seen.add(country)
            result.append({"name": country})
    return sorted(result, key=lambda x: x["name"])


def build_channels_map(channels: list[dict]) -> dict[str, dict]:
    """Build {url: channel} lookup dict."""
    return {ch["url"]: ch for ch in channels if ch.get("url")}


def build_favorites_set(state_obj) -> set[str]:
    """Extract a set of favorite URLs from observable state."""
    favs = state_obj.favorites
    if isinstance(favs, set):
        return favs
    if isinstance(favs, list):
        return set(favs)
    return set()


def extract_categories(channels: list[dict]) -> list[str]:
    """Derive sorted category list from channel data."""
    seen = set()
    result = []
    for c in channels:
        group = c.get("group", "General")
        if group and group not in seen:
            seen.add(group)
            result.append(group)
    return sorted(result)
