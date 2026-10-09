"""Shared history-entry helpers for the history screen and carousel.

Both views previously duplicated _display_name + logo resolution (and both
got it wrong in the same ways: entry.get before isinstance, raw-URL
subtitles leaking credentials, no logo-cache warmup). One helper, one fix.
"""

import contextlib
import os
from collections.abc import Callable
from urllib.parse import unquote, urlparse

from services.logo_cache import enqueue_logo_download, get_cached_logo

# on_play contract: every handler takes (url, title=None). One-arg calls keep
# working because title defaults to None.
OnPlayHandler = Callable[..., None]


def display_name(url: str | None) -> str:
    """Human title fallback for a URL with no stored title.

    Strips query/fragment, URL-decodes, and falls back to the host for
    extension-less URLs (numeric IDs, trailing slashes) instead of junk.
    """
    if not url or not isinstance(url, str):
        return "Stream"
    try:
        parsed = urlparse(url)
    except Exception:
        return "Stream"
    path = unquote(parsed.path or "")
    name = os.path.splitext(os.path.basename(path.rstrip("/")))[0]
    if name:
        return name
    if parsed.hostname:
        return parsed.hostname
    return "Stream"


def resolve_entry(
    entry: dict | str, channels_map: dict[str, dict]
) -> tuple[str, str | None, str, str] | None:
    """Normalize one history entry to (url, stored_title, title, logo_src).

    Returns None for entries with no usable URL (caller skips them).
    isinstance-first: legacy plain-string entries never touch .get.
    """
    if isinstance(entry, str):
        url = entry
        stored_title: str | None = None
        title = channels_map.get(url, {}).get("name") or display_name(url)
        logo = channels_map.get(url, {}).get("logo", "")
    elif isinstance(entry, dict):
        url = entry.get("url") or ""
        if not isinstance(url, str) or not url:
            return None
        stored_title = entry.get("title")
        if not isinstance(stored_title, str):
            stored_title = None
        title = (
            stored_title or channels_map.get(url, {}).get("name") or display_name(url)
        )
        logo = channels_map.get(url, {}).get("logo", "") or entry.get("logo", "")
    else:
        return None
    return url, stored_title, title, _resolve_logo(url, logo)


def _resolve_logo(url: str, logo: object) -> str:
    """Resolve a logo to an Image src, warming the disk cache on miss."""
    logo_src = logo if isinstance(logo, str) and logo else "/icon.png"
    if logo_src.startswith(("/", "data:")):
        return logo_src
    cached = get_cached_logo(logo_src)
    if cached:
        return cached
    # Miss: hand the remote URL to Image for this frame but enqueue the
    # size-capped streaming download so the disk cache warms for next time.
    with contextlib.suppress(Exception):
        enqueue_logo_download(logo_src)
    return logo_src
