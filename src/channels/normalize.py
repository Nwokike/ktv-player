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
- ``country_code`` real ISO code when the country is known, ``""`` otherwise
                   (kept for legacy callers: get_countries, search)

Source-aware on purpose: the premium normalizer never runs the legacy
regex, so iptv-org's ``Entertainment``/``Series``/``Undefined`` tags can
never masquerade as country folders.
"""

import re

from core.country_codes import country_name

NON_COUNTRY_GROUPS = frozenset(
    {
        "movies",
        "movie",
        "news",
        "sports",
        "sport",
        "documentaries",
        "documentary",
        "music",
        "kids",
        "kid",
        "comedy",
        "vod",
        "business",
        "weather",
        "lifestyle",
        "religious",
        "education",
        "general",
        "entertainment",
        "series",
        "animation",
        "undefined",
        "other",
        "custom",
    }
)

# One precompiled pattern for all category words (case-insensitive): ~140k
# per-channel regex compiles for a 10k playlist become a single match.
_NON_COUNTRY_RE = re.compile(
    r"(^|\W)(?:" + "|".join(sorted(NON_COUNTRY_GROUPS)) + r")(?=\W|$)",
    re.IGNORECASE,
)

_TVG_ID_CODE_RE = re.compile(r"[a-z]{2,3}$")

# Multi-value tvg-country separators seen in the wild ("us;uk", "US,GB").
_COUNTRY_SPLIT_RE = re.compile(r"[;,|/\s]+")


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


def tvg_id_country_validated(tvg_id: str) -> tuple[str | None, str | None]:
    """(code, country_name) for a tvg-id, validated against the code table.

    A bare 2-3 letter suffix is NOT enough: ``News.HD`` yields ``hd`` which
    matches the shape but is not a country. Unknown suffixes return
    (None, None) so callers fall through to tvg_country instead of locking
    in Global.
    """
    code = tvg_id_country(tvg_id)
    if not code:
        return None, None
    name = country_name(code)
    if name is None:
        return None, None
    return code, name


def _is_category_word(segment: str) -> bool:
    return bool(_NON_COUNTRY_RE.search(segment or ""))


def _split(group: str) -> list[str]:
    return [p.strip() for p in str(group or "").split(";") if p.strip()]


def _canonical_country(raw: str) -> str:
    """Title-case canonical form so Nigeria/nigeria/NIGERIA share one folder.

    Acronyms survive: USA/UK/UAE/U.S. are upper-cased rather than
    down-cased ("Usa", "Uk", "U.S." -> "U.s."). Naive title-casing renamed
    real legacy folders deterministically, splitting saved filters and the
    country pill (both match exact strings).
    """
    out: list[str] = []
    for word in str(raw or "").split():
        letters = word.replace(".", "")
        if letters.isupper() and (len(letters) <= 4 or "." in word):
            out.append(word.upper())  # USA, UK, UAE, U.S.
        else:
            out.append(word[:1].upper() + word[1:].lower())
    return " ".join(out)


def _first_known_country_code(raw: str) -> tuple[str | None, str | None]:
    """First (code, name) in a possibly multi-value tvg-country field."""
    for part in _COUNTRY_SPLIT_RE.split(str(raw or "").strip().lower()):
        if not part:
            continue
        name = country_name(part)
        if name is not None:
            return part, name
    return None, None


def normalize_legacy(channels: list[dict]) -> list[dict]:
    """Free base + anything that keeps country inside group-title."""
    for c in channels:
        parts = _split(c.get("group", "General")) or ["General"]
        first = parts[0]
        country = None if _is_category_word(first) else _canonical_country(first)
        c["country"] = country or "Global"
        # Single-country legacy channels carry NO category (not even General):
        # they must not surface under any category filter. Multi-part groups
        # keep their trailing tags as categories.
        c["categories"] = parts[1:] if country else parts
        c["country_code"] = "M3U" if country else ""
        c.setdefault("is_custom", False)
    return channels


def normalize_premium(channels: list[dict]) -> list[dict]:
    """Premium pack: real countries from tvg-id, all tags as categories."""
    for c in channels:
        code, name = tvg_id_country_validated(c.get("tvg_id", ""))
        if name is None:
            code, name = _first_known_country_code(c.get("tvg_country", ""))
        c["country"] = name or "Global"
        # Tag-set order is meaningless upstream; keep first-seen order and
        # drop case-insensitive duplicates so counts stay honest.
        seen: set[str] = set()
        cats: list[str] = []
        for tag in _split(c.get("group", "")):
            key = tag.casefold()
            if key not in seen:
                seen.add(key)
                cats.append(tag)
        c["categories"] = cats
        c["country_code"] = code if name else ""
        c.setdefault("is_custom", False)
    return channels
