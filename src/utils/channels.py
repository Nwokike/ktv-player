"""Channel utility functions for components components."""


def extract_countries(channels: list[dict]) -> list[str]:
    """Derive sorted country list from channel data. Returns strings."""
    seen = set()
    result = []
    for c in channels:
        if c.get("is_custom"):
            continue
        original_group = c.get("group", "General")
        parts = [p.strip() for p in original_group.split(";")]
        country = parts[0] if c.get("country_code") else "Global"
        if country and country not in seen:
            seen.add(country)
            result.append(country)
    return sorted(result)


def extract_country_dicts(channels: list[dict]) -> list[dict]:
    """Derive sorted country list from channel data. Returns dicts with 'name' key, ending with 'Other'."""
    seen = set()
    result = []
    for c in channels:
        if c.get("is_custom"):
            continue
        original_group = c.get("group", "General")
        parts = [p.strip() for p in original_group.split(";")]
        country = parts[0] if c.get("country_code") else "Global"
        if country and country != "Other" and country not in seen:
            seen.add(country)
            result.append({"name": country})
    sorted_res = sorted(result, key=lambda x: x["name"])
    sorted_res.append({"name": "Other"})
    return sorted_res


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
        if c.get("is_custom"):
            continue
        original_group = c.get("group", "General")
        parts = [p.strip() for p in original_group.split(";")]
        category = (
            parts[-1]
            if len(parts) > 1
            else (parts[0] if not c.get("country_code") else "General")
        )
        if category and category.lower() != "general" and category not in seen:
            seen.add(category)
            result.append(category)
    return sorted(result)


def extract_country_counts(channels: list[dict]) -> dict[str, int]:
    """Derive mapping of country names to channel counts from channel data."""
    from collections import Counter

    counts: Counter[str] = Counter()
    for c in channels:
        if c.get("is_custom"):
            continue
        original_group = c.get("group", "General")
        parts = [p.strip() for p in original_group.split(";")]
        country = parts[0] if c.get("country_code") else "Global"
        if country:
            counts[country] += 1
    return dict(counts)


def extract_category_counts(channels: list[dict]) -> dict[str, int]:
    """Derive mapping of category names to channel counts from channel data."""
    from collections import Counter

    counts: Counter[str] = Counter()
    for c in channels:
        if c.get("is_custom"):
            continue
        original_group = c.get("group", "General")
        parts = [p.strip() for p in original_group.split(";")]
        category = (
            parts[-1]
            if len(parts) > 1
            else (parts[0] if not c.get("country_code") else "General")
        )
        if category and category.lower() != "general":
            counts[category] += 1
    return dict(counts)


def extract_custom_groups(channels: list[dict]) -> list[str]:
    """Derive sorted unique groups from custom channels (M3U group-title)."""
    from collections import Counter

    counts: Counter[str] = Counter()
    for c in channels:
        if not c.get("is_custom"):
            continue
        group = c.get("group", "")
        if not group or group.lower() == "custom":
            continue
        # Split on ; to handle multi-group titles like "Entertainment;Kids"
        for part in group.split(";"):
            g = part.strip()
            if g and g.lower() not in ("general", "undefined"):
                counts[g] += 1
    return [g for g, _ in counts.most_common()]


def extract_custom_group_counts(channels: list[dict]) -> dict[str, int]:
    """Derive mapping of custom group names to channel counts from M3U group-title."""
    from collections import Counter

    counts: Counter[str] = Counter()
    for c in channels:
        if not c.get("is_custom"):
            continue
        group = c.get("group", "")
        if not group or group.lower() == "custom":
            continue
        for part in group.split(";"):
            g = part.strip()
            if g and g.lower() not in ("general", "undefined"):
                counts[g] += 1
    return dict(counts)
