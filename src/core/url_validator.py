"""URL validation helper for stream play URLs."""

import re
import urllib.parse

_SENSITIVE_PATHS = (
    "/etc/",
    "/proc/",
    "/sys/",
    "/dev/",
    "C:\\Windows",
    "C:/Windows",
    "C:\\System",
    "C:/System",
    "/data/data/",
    "/data/user/",
)


def _is_valid_play_url(raw: str) -> bool:
    if not raw or len(raw) > 4096:
        return False

    if raw.startswith(("file://", "content://")):
        lower = raw.lower()
        return not any(s.lower() in lower for s in _SENSITIVE_PATHS)

    for scheme in ("http://", "https://", "rtsp://", "rtmp://", "rtp://", "mms://"):
        if raw.startswith(scheme):
            try:
                urllib.parse.urlparse(raw)
                return True
            except Exception:
                return False

    if re.match(r"^[A-Za-z]:\\", raw) or raw.startswith("/"):
        lower = raw.lower()
        return not any(s.lower() in lower for s in _SENSITIVE_PATHS)

    return False
