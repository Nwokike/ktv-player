"""Deep link parsing and decoding for KTV Player."""

import base64
import logging
import urllib.parse

from core.url_validator import _is_valid_play_url

logger = logging.getLogger(__name__)


def parse_deep_link(route: str) -> tuple[str | None, str | None]:
    """Parse ktv:// deep link and return (decoded_url, decoded_title)."""
    try:
        parsed = urllib.parse.urlparse(route)
        query = urllib.parse.parse_qs(parsed.query)

        encoded = query.get("url", [None])[0]
        if not encoded:
            return None, None

        padding_needed = (4 - len(encoded) % 4) % 4
        encoded_padded = encoded + ("=" * padding_needed)
        decoded = base64.urlsafe_b64decode(encoded_padded).decode("utf-8")

        if not _is_valid_play_url(decoded):
            logger.warning("Deep link decoded invalid URL: %s", decoded[:80])
            return None, None

        title = None
        encoded_title = query.get("title", [None])[0]
        if encoded_title:
            try:
                padding_needed = (4 - len(encoded_title) % 4) % 4
                encoded_padded = encoded_title + ("=" * padding_needed)
                title = base64.urlsafe_b64decode(encoded_padded).decode("utf-8")
            except Exception:
                logger.warning("Failed to decode deep link title")

        return decoded, title
    except Exception:
        logger.exception("Failed to decode deep link")
        return None, None
