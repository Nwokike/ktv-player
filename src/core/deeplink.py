"""Deep link parsing and decoding for KTV Player."""

import base64
import json
import logging
import re
import urllib.parse

from core.url_validator import is_valid_deeplink_url

logger = logging.getLogger(__name__)

# CPU/memory DoS guard: a 10MB query param must never reach b64decode.
_MAX_B64 = 8192

_BLOCKED_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "transfer-encoding",
        "connection",
        "authorization",
        "cookie",
    }
)

_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]+={0,2}$")


def _b64(s: str) -> str:
    """Strict urlsafe-b64 decode with cap. validate=True rejects the
    non-alphabet chars the default silently discards (masking malformed
    input); the length cap bounds CPU/memory up front. (urlsafe_b64decode
    takes no validate flag, so translate to standard alphabet first.)
    """
    s = s.replace(" ", "+").strip()
    if not s or len(s) > _MAX_B64:
        raise ValueError("bad base64 length")
    s += "=" * ((4 - len(s) % 4) % 4)
    std = s.replace("-", "+").replace("_", "/")
    return base64.b64decode(std, validate=True).decode("utf-8")


def _decode_title(raw: str) -> str:
    """Base64 only when it looks like base64 AND round-trips.

    The old try-b64-first rule misdecoded any alphanumeric plaintext that
    happened to be valid base64 alphabet (e.g. title "abcd" → garbage
    bytes). isprintable() also rejected legitimate newlines.
    """
    if _B64URL_RE.fullmatch(raw):
        try:
            decoded = _b64(raw)
            if decoded and base64.urlsafe_b64encode(
                decoded.encode("utf-8")
            ).decode().rstrip("=") == raw.rstrip("="):
                return decoded
        except Exception:
            pass
        logger.debug("Deep link title is not round-trip base64; using raw")
    return raw


def _decode_headers(raw: str) -> dict | None:
    """Validated header map or None. Enforces: dict shape, ≤32 keys, str
    keys ≤64 / values ≤2048, no CRLF (response-split), blocklisted names
    dropped with a log line (Host/Content-Length/Authorization/Cookie must
    never ride in from an external link)."""
    try:
        payload = json.loads(_b64(raw))
    except Exception:
        logger.debug("Deep link headers are not valid base64 JSON")
        return None
    if not isinstance(payload, dict):
        logger.debug("Deep link headers are not an object")
        return None
    if len(payload) > 32:
        logger.debug("Deep link headers exceed 32 keys")
        return None
    clean: dict[str, str] = {}
    for k, v in payload.items():
        if not isinstance(k, str) or not isinstance(v, str):
            logger.debug("Deep link header with non-string key/value dropped")
            return None
        if len(k) > 64 or len(v) > 2048:
            logger.debug("Deep link header key/value too long")
            return None
        if "\r" in k or "\n" in k or "\r" in v or "\n" in v:
            logger.debug("Deep link header with CRLF dropped")
            return None
        if k.strip().lower() in _BLOCKED_HEADERS:
            logger.debug("Deep link header %r blocked", k)
            continue
        clean[k.strip()] = v.strip()
    return clean


def parse_deep_link(
    route: str,
) -> tuple[str | None, str | None, str | None, dict | None]:
    """Parse ktv:// deep link and return (decoded_url, decoded_title, decoded_referer, decoded_headers)."""
    try:
        parsed = urllib.parse.urlparse(route)
        # Gate here, not just at the caller: this function is unsafe for
        # reuse on arbitrary URLs (it used to accept https://evil.com?url=).
        if parsed.scheme != "ktv" or parsed.netloc not in ("play", ""):
            return None, None, None, None
        query = urllib.parse.parse_qs(parsed.query)

        encoded = query.get("url", [None])[0]
        if not encoded:
            return None, None, None, None

        try:
            decoded = _b64(encoded).strip()
        except Exception:
            return None, None, None, None

        # Network-only for external links: file:// / content:// / absolute
        # paths are valid IN-APP play URLs but must never arrive via an
        # external intent (arbitrary local file open).
        if not is_valid_deeplink_url(decoded):
            logger.debug("Deep link URL rejected")
            return None, None, None, None

        title = None
        raw_title = query.get("title", [None])[0]
        if raw_title:
            title = _decode_title(raw_title)

        referer = None
        raw_referer = query.get("referer", [None])[0]
        if raw_referer:
            try:
                candidate = _b64(raw_referer).strip()
            except Exception:
                candidate = raw_referer.strip()
            if (
                candidate.lower().startswith(("http://", "https://"))
                and "\r" not in candidate
                and "\n" not in candidate
            ):
                referer = candidate
            else:
                logger.debug("Deep link referer rejected")

        headers = None
        raw_headers = query.get("headers", [None])[0]
        if raw_headers:
            # Base64-only: raw JSON containing & or = would already have been
            # split apart by parse_qs upstream — accepting it here was fragile.
            headers = _decode_headers(raw_headers)

        return decoded, title, referer, headers
    except Exception:
        logger.exception("Failed to decode deep link")
        return None, None, None, None
