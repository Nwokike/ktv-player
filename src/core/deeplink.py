"""Deep link parsing and decoding for KTV Player."""

import base64
import logging
import urllib.parse

from core.url_validator import _is_valid_play_url

logger = logging.getLogger(__name__)


def parse_deep_link(
    route: str,
) -> tuple[str | None, str | None, str | None, dict | None]:
    """Parse ktv:// deep link and return (decoded_url, decoded_title, decoded_referer, decoded_headers)."""
    try:
        parsed = urllib.parse.urlparse(route)
        query = urllib.parse.parse_qs(parsed.query)

        encoded = query.get("url", [None])[0]
        if not encoded:
            return None, None, None, None

        padding_needed = (4 - len(encoded) % 4) % 4
        encoded_padded = encoded + ("=" * padding_needed)
        decoded = base64.urlsafe_b64decode(encoded_padded).decode("utf-8")

        if not _is_valid_play_url(decoded):
            logger.warning("Deep link decoded invalid URL: %s", decoded[:80])
            return None, None, None, None

        title = None
        raw_title = query.get("title", [None])[0]
        if raw_title:
            try:
                padding_needed = (4 - len(raw_title) % 4) % 4
                encoded_padded = raw_title + ("=" * padding_needed)
                decoded_title = base64.urlsafe_b64decode(encoded_padded).decode("utf-8")
                # Prefer base64 decoded title if valid printable text, otherwise use raw title
                if decoded_title and decoded_title.isprintable():
                    title = decoded_title
                else:
                    title = raw_title
            except Exception:
                title = raw_title

        referer = None
        raw_referer = query.get("referer", [None])[0]
        if raw_referer:
            try:
                padding_needed = (4 - len(raw_referer) % 4) % 4
                encoded_padded = raw_referer + ("=" * padding_needed)
                referer = base64.urlsafe_b64decode(encoded_padded).decode("utf-8")
            except Exception:
                referer = raw_referer

        headers = None
        raw_headers = query.get("headers", [None])[0]
        if raw_headers:
            try:
                padding_needed = (4 - len(raw_headers) % 4) % 4
                encoded_padded = raw_headers + ("=" * padding_needed)
                import json

                headers = json.loads(
                    base64.urlsafe_b64decode(encoded_padded).decode("utf-8")
                )
            except Exception:
                try:
                    import json

                    headers = json.loads(raw_headers)
                except Exception:
                    pass

        return decoded, title, referer, headers
    except Exception:
        logger.exception("Failed to decode deep link")
        return None, None, None, None
