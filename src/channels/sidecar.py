"""Parsed-playlist sidecar: msgpack snapshot of the normalized channel
list beside each raw .m3u8 cache file (Phase 8 cold-start win).

The provider's hot path used to re-parse multi-MB playlist text on every
launch (regex over ~140k lines on the event loop). The sidecar stores
the parse RESULT, validated against the raw file's mtime + size: any
change (refresh, truncation, external cleaner) invalidates it, and a
corrupt/stale sidecar falls back to a normal parse. The raw .m3u8 stays
the source of truth; the sidecar is pure cache and safe to delete.

Compact row encoding: channels are stored as positional LISTS under a
fixed field order (declared in _FIELDS), not dicts — dict keys repeated
per row cost ~36% extra bytes at 30k channels (measured 6.1MB vs 4.5MB
raw). _SCHEMA_VERSION bumps if the field order ever changes; old files
mismatch and re-parse.
"""

import logging
import os

import msgpack

logger = logging.getLogger(__name__)

_SCHEMA_VERSION = 2

# Fixed positional field order. Ordered to match normalize.py's contract
# (url/name/logo/group/country first — the hot lookup keys).
_FIELDS = (
    "url",
    "name",
    "logo",
    "group",
    "country",
    "country_code",
    "categories",
    "tvg_id",
    "tvg_country",
    "is_custom",
)


def sidecar_path(text_path: str) -> str:
    return text_path + ".mpk"


def _encode(channels: list[dict]) -> list[list]:
    rows = []
    for ch in channels:
        try:
            rows.append([ch.get(f) for f in _FIELDS])
        except Exception:
            return []
    return rows


def _decode(rows: list) -> list[dict] | None:
    channels = []
    for row in rows:
        if not isinstance(row, list) or len(row) != len(_FIELDS):
            return None
        channels.append(dict(zip(_FIELDS, row, strict=True)))
    return channels


def load_sidecar(text_path: str) -> list[dict] | None:
    """Channels from the sidecar when it matches the raw file, else None.

    Sync on purpose: get_countries()'s disk-only path is sync and a
    msgpack unpack of even 15k rows is single-digit-to-tens-of-ms — the
    regex parse it replaces is the expensive step.
    """
    try:
        st = os.stat(text_path)
    except OSError:
        return None
    try:
        with open(sidecar_path(text_path), "rb") as f:
            raw = f.read()
        decoded = msgpack.unpackb(raw, raw=False, strict_map_key=False)
        if not isinstance(decoded, dict) or decoded.get("v") != _SCHEMA_VERSION:
            return None
        if decoded.get("mtime") != st.st_mtime or decoded.get("size") != st.st_size:
            return None
        rows = decoded.get("rows")
        if not isinstance(rows, list) or not rows:
            return None
        return _decode(rows)
    except (OSError, ValueError, TypeError, msgpack.UnpackException):
        logger.debug("Sidecar load failed for %s", text_path, exc_info=True)
        return None


def store_sidecar(text_path: str, channels: list[dict]) -> None:
    """Write the sidecar for a raw text file. Best-effort: a failure must
    never take down the load path (the next launch just re-parses)."""
    try:
        rows = _encode(channels)
        if not rows:
            return
        st = os.stat(text_path)
        payload = msgpack.packb(
            {
                "v": _SCHEMA_VERSION,
                "mtime": st.st_mtime,
                "size": st.st_size,
                "rows": rows,
            },
            use_bin_type=True,
        )
        tmp = sidecar_path(text_path) + ".tmp"
        with open(tmp, "wb") as f:
            f.write(payload)
        os.replace(tmp, sidecar_path(text_path))
    except (OSError, ValueError, TypeError, msgpack.PackException):
        logger.debug("Sidecar store failed for %s", text_path, exc_info=True)
