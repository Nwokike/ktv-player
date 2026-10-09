"""URL validation helper for stream play URLs."""

import re
import urllib.parse

from core.constants import (
    MAX_URL_LENGTH,
    SENSITIVE_PATHS,
    VALID_STREAM_SCHEMES,
)

_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _reject_dirty(s: str) -> bool:
    """True when the raw string must be rejected outright: leading/trailing
    whitespace (paste artifacts), interior control chars (log/header
    injection, SSRF obfuscation), or a stripped form that differs."""
    if s != s.strip():
        return True
    return bool(_CONTROL_RE.search(s))


def _sensitive_hit(lowered_unquoted_path: str) -> bool:
    return any(s.lower() in lowered_unquoted_path for s in SENSITIVE_PATHS)


def _is_valid_play_url(raw: str) -> bool:
    return is_valid_play_url(raw)


def is_valid_play_url(raw: object) -> bool:
    """Public validator: True for playable stream/file URLs.

    (Renamed from private `_is_valid_play_url` — it is imported across
    modules (main, deeplink) and underscore-invited duplication. The old
    name remains as a compat alias above.)
    """
    if not isinstance(raw, str):
        return False
    if not raw or len(raw) > MAX_URL_LENGTH:
        return False
    if _reject_dirty(raw):
        return False

    low = raw.lower()
    if low.startswith(("file://", "content://")):
        path = urllib.parse.unquote(raw).lower()
        without_scheme = path.split("://", 1)[1] if "://" in path else ""
        if not without_scheme:
            return False
        normalized = without_scheme.replace("\\", "/")
        parts = [p for p in normalized.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            return False
        return not _sensitive_hit("/" + "/".join(parts) + "/")

    for scheme in VALID_STREAM_SCHEMES:
        if low.startswith(scheme):
            try:
                parsed = urllib.parse.urlparse(raw)
            except Exception:
                return False
            if not parsed.hostname:
                return False
            # Any whitespace anywhere (netloc OR path/query): unencoded
            # spaces are invalid in URIs and risky downstream (shell, logs,
            # header construction). Callers must percent-encode.
            if any(c.isspace() for c in raw):
                return False
            # Credentials in playlist URLs are phishing-prone
            # (http://example.com@evil.com/): reject userinfo outright.
            return not (parsed.username or parsed.password)

    if re.match(r"^[A-Za-z]:[\\/]", raw) or raw.startswith("/"):
        if raw.startswith("//"):
            return False
        path = urllib.parse.unquote(raw).lower().replace("\\", "/")
        parts = [p for p in path.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            return False
        # A bare drive root ("C:/") keeps its "c:" part after the split;
        # require at least one component BEYOND the drive/empty form.
        if not parts or (len(parts) == 1 and re.fullmatch(r"[a-z]:", parts[0])):
            return False
        return not _sensitive_hit("/" + "/".join(parts) + "/")

    return False


def is_valid_deeplink_url(raw: object) -> bool:
    """Network-only variant for EXTERNAL deep links (ktv://).

    Local file/content URLs are valid play URLs in-app (Local screen, Open
    With) but must never arrive via an external intent: a malicious link
    could otherwise make the app open arbitrary local files.
    """
    if not isinstance(raw, str) or not raw:
        return False
    low = raw.lower()
    allowed = ("http://", "https://", "rtsp://", "rtmp://")
    if not low.startswith(allowed):
        return False
    return is_valid_play_url(raw)


def is_local_media_url(raw: str) -> bool:
    """True for on-device media (absolute paths, file://, content://, Windows
    drive letters) as opposed to network streams."""
    if not isinstance(raw, str) or not raw:
        return False
    low = raw.lower()
    if low.startswith("//"):
        return False
    if low.startswith(("file://", "content://", "/")):
        return True
    return bool(re.match(r"^[A-Za-z]:[\\/]", raw))
