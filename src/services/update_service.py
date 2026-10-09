"""Update service — checks version.json on the repo's main branch and
reports whether a newer build is available (or an announcement is set).

Deliberately browser-based delivery, like both reference apps: the
dialog launches the release/Play Store URL externally; there is no
in-app APK download or install.
"""

import logging
import time
from dataclasses import dataclass

import httpx

from core.constants import (
    APP_BUILD_NUMBER,
    APP_VERSION,
    GITHUB_RELEASES_URL,
    UPDATE_CONFIG_URL,
    USER_AGENT,
)
from services.http_client import get_http_client

logger = logging.getLogger(__name__)

_UPDATE_TIMEOUT = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
# Don't hit the network on every Settings open: cache the last verdict.
_CHECK_TTL = 300.0

_ANNOUNCEMENT_TYPES = ("announcement", "notice")


def _parse_mandatory(raw: object) -> bool:
    """bool("false") is True — parse explicitly or a string payload forces a
    mandatory update on every client."""
    if isinstance(raw, str):
        return raw.strip().lower() in ("true", "1", "yes")
    return raw in (True, 1)


def _coerce_str(raw: object, default: str = "") -> str:
    return raw if isinstance(raw, str) else default


@dataclass
class UpdateInfo:
    version: str
    build_number: int
    type: str = "update"
    title: str = ""
    release_notes: str = ""
    mandatory: bool = False
    github_url: str = GITHUB_RELEASES_URL
    playstore_url: str | None = None

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "build_number": self.build_number,
            "type": self.type,
            "title": self.title,
            "release_notes": self.release_notes,
            "mandatory": self.mandatory,
            "github_url": self.github_url,
            "playstore_url": self.playstore_url,
        }


class UpdateService:
    def __init__(self, config_url: str = UPDATE_CONFIG_URL):
        if not isinstance(config_url, str) or not config_url.startswith("https://"):
            raise ValueError(f"Update config URL must be https: {config_url!r}")
        self.config_url = config_url
        self._last_check: float = 0.0
        self._last_result: UpdateInfo | None = None

    async def check_for_update(
        self, notify_if_latest: bool = False
    ) -> UpdateInfo | None:
        """Return an UpdateInfo when the server build is newer or an
        announcement is set, else None. Every failure path is silent —
        an offline or unreachable check must never disturb the user.

        Returns the dataclass (not a dict): callers get attribute access and
        the contract is unambiguous. Results cached for _CHECK_TTL so opening
        Settings repeatedly doesn't hammer the network.
        """
        now = time.time()
        if now - self._last_check < _CHECK_TTL:
            return self._last_result
        try:
            result = await self._fetch()
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as ex:
            logger.debug("Update check failed (expected if offline): %s", ex)
            return None
        except Exception as ex:
            # Programming bugs must surface in debug; still silent to users.
            logger.warning("Update check unexpected error: %s", ex, exc_info=True)
            return None
        self._last_check = now
        self._last_result = result
        return result

    async def _fetch(self) -> UpdateInfo | None:
        client = get_http_client()
        resp = await client.get(
            self.config_url,
            timeout=_UPDATE_TIMEOUT,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
        )
        if resp.status_code != 200:
            logger.debug("Update check non-200: %s", resp.status_code)
            return None
        data = resp.json()
        if not isinstance(data, dict):
            logger.warning("Update payload is not a JSON object")
            return None

        info_type = data.get("type", "update")
        if not isinstance(info_type, str):
            info_type = "update"

        # Announcements deliver on the SAME build (the old gate returned
        # None before reaching them, so notices never displayed).
        if info_type in _ANNOUNCEMENT_TYPES:
            return self._build_info(data, info_type, announcement=True)

        server_build = data.get("build_number", 0)
        if isinstance(server_build, bool) or not isinstance(server_build, int):
            # bool IS int in Python: True would compare as build 1. Numeric
            # strings / floats are a publisher error, not an update.
            logger.warning("Update payload has invalid build_number: %r", server_build)
            return None
        if "build_number" not in data:
            logger.warning("Update payload missing build_number; no update")
            return None
        if server_build <= APP_BUILD_NUMBER:
            return None
        return self._build_info(data, info_type, announcement=False)

    def _build_info(self, data: dict, info_type: str, announcement: bool) -> UpdateInfo:
        version = _coerce_str(data.get("version"), APP_VERSION)
        title = _coerce_str(data.get("title")) or (
            data.get("announcement_title", "")
            if announcement
            else f"Version {version} Available!"
        )
        title = title if isinstance(title, str) else f"Version {version} Available!"
        github_url = _coerce_str(data.get("github_url")) or GITHUB_RELEASES_URL
        playstore_url = data.get("playstore_url") or None
        if playstore_url is not None and not isinstance(playstore_url, str):
            playstore_url = None
        return UpdateInfo(
            version=version,
            build_number=data.get("build_number", APP_BUILD_NUMBER)
            if isinstance(data.get("build_number"), int)
            else APP_BUILD_NUMBER,
            type=info_type,
            title=title,
            release_notes=_coerce_str(data.get("release_notes")),
            mandatory=_parse_mandatory(data.get("mandatory", False)),
            github_url=github_url,
            playstore_url=playstore_url,
        )
