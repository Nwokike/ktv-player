"""Normalize parsed M3U channels into canonical country + categories.

Two taxonomies meet here:

- **Legacy sources** (Free-TV base, user playlists): the country IS the
  group-title. A group is a country when its FIRST segment is not a
  category word, so ``Nigeria;News`` keeps Nigeria (the old whole-string
  scan threw the country away whenever any category word appeared).
- **The premium pack** (iptv-org): group-title is an unordered category
  tag-set only (``News;Public``, up to 6 tags). Country exists solely
  inside tvg-id (``1Plus1Marafon.ua@SD`` -> ``ua`` -> Ukraine).

Every normalized channel gains:

- ``country``      display folder for the Country pill (``Global`` fallback)
- ``categories``   every category tag for the Category pill
- ``country_code`` ``"M3U"`` when it has a real country, ``""`` otherwise
                   (kept for legacy callers: get_countries, search)

Source-aware on purpose: the premium normalizer never runs the legacy
regex, so iptv-org's ``Entertainment``/``Series``/``Undefined`` tags can
never masquerade as country folders.
"""

import re

from core.country_codes import country_name

NON_COUNTRY_GROUPS = {
    "movies",
    "news",
    "sports",
    "documentaries",
    "music",
    "kids",
    "comedy",
    "vod",
    "business",
    "weather",
    "lifestyle",
    "religious",
    "education",
    "general",
}

_TVG_ID_CODE_RE = re.compile(r"[a-z]{2,3}$")


def tvg_id_country(tvg_id: str) -> str | None:
    """Lowercase country code embedded in a tvg-id, or None.

    Handles both shapes in the wild: ``Name.ua@SD`` (premium pack) and
    ``Kanali7.al`` (Free-TV). The feed marker after ``@`` is dropped
    first, then the suffix after the final dot is validated as a code.
    """
    base = str(tvg_id or "").split("@", 1)[0].strip()
    if "." not in base:
        return None
    code = base.rsplit(".", 1)[1].lower()
    return code if _TVG_ID_CODE_RE.fullmatch(code) else None


def _is_category_word(segment: str) -> bool:
    lower = segment.lower()
    return any(
        bool(re.search(rf"(^|\W){word}(\W|$)", lower)) for word in NON_COUNTRY_GROUPS
    )


def _split(group: str) -> list[str]:
    return [p.strip() for p in str(group or "").split(";") if p.strip()]


def normalize_legacy(channels: list[dict]) -> list[dict]:
    """Free base + anything that keeps country inside group-title."""
    for c in channels:
        parts = _split(c.get("group", "General")) or ["General"]
        first = parts[0]
        country = None if _is_category_word(first) else first
        c["country"] = country or "Global"
        c["categories"] = parts[1:] if country else parts
        c["country_code"] = "M3U" if country else ""
        c["is_custom"] = False
    return channels


def normalize_premium(channels: list[dict]) -> list[dict]:
    """Premium pack: real countries from tvg-id, all tags as categories."""
    for c in channels:
        code = tvg_id_country(c.get("tvg_id", "")) or (
            str(c.get("tvg_country", "")).strip().lower() or None
        )
        name = country_name(code) if code else None
        c["country"] = name or "Global"
        # Tag-set order is meaningless upstream; keep first-seen order and
        # drop exact duplicates so counts stay honest.
        c["categories"] = list(dict.fromkeys(_split(c.get("group", ""))))
        c["country_code"] = "M3U" if name else ""
        c["is_custom"] = False
    return channels
