from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

import flet as ft

from core.constants import MAX_HISTORY_ITEMS

if TYPE_CHECKING:
    from services.update_service import UpdateInfo


@ft.observable
@dataclass
class AppState:
    is_loading: bool = False
    is_online: bool = True
    channels: list[dict] | None = None
    history: list[dict] | None = None
    favorites: list[str] | None = None

    user_country: str = ""
    has_accepted_terms: bool = False
    is_first_launch: bool = True
    # NOTE: theme lives on page.theme_mode (see main.py boot restore and
    # utils/theme_utils.toggle_theme). There is intentionally NO theme_mode
    # field here — a second source of truth would diverge silently.
    is_deep_link_launch: bool = False

    channels_hash: str = ""

    # Update service (version dialog reads these; None/False = up to date).
    # UpdateInfo dataclass (not a dict): attribute access, unambiguous contract.
    update_available: bool = False
    update_data: UpdateInfo | None = None

    # Premium (remove-ads) unlock — derived at boot from the verified Kiri
    # License token (services.kiri_license / license_token), never from a
    # bare setting.
    is_premium: bool = False

    def __post_init__(self):
        # @ft.observable + @dataclass: observable handles notification,
        # dataclass gives real per-instance lists (no shared Field objects).
        if self.channels is None:
            self.channels = []
        if self.history is None:
            self.history = []
        if self.favorites is None:
            self.favorites = []

    def add_to_history(self, url: str, title: str = ""):
        # Normalize: store as dict with url and title, carrying forward any saved position/duration
        if not isinstance(url, str) or not url:
            return
        existing = next(
            (e for e in self.history if isinstance(e, dict) and e.get("url") == url),
            None,
        )
        if isinstance(existing, dict):
            old_title = existing.get("title")
            entry: dict = {
                "url": url,
                "title": title or old_title or url,
            }
            if existing.get("position") is not None:
                entry["position"] = existing["position"]
            if existing.get("duration") is not None:
                entry["duration"] = existing["duration"]
        else:
            entry = {"url": url, "title": title or url}
        # Single assignment → single notify (no reassign+insert+slice triple).
        rest = [
            e for e in self.history if not (isinstance(e, dict) and e.get("url") == url)
        ]
        self.history = [entry, *rest][:MAX_HISTORY_ITEMS]

    def set_channels(self, channels: list[dict]):
        self.channels = list(channels)  # copy, not direct reference
        # Hash covers taxonomy too, not just URLs: a playlist swap that
        # reuses stream URLs but renames every group must still bump the
        # hash, or every use_memo (pills, grid, counts) keeps serving the
        # old folders. country is included because it can change while
        # url+group stay identical (tvg-id remapping). Order-sensitive
        # sha256 (not salted sum): reordering must bump too. Empty stays ""
        # so `if channels_hash` keeps working as a loaded-check.
        rows = [
            f"{c.get('url', '')}|{c.get('group', '')}|{c.get('country', '')}|{c.get('name', '')}"
            for c in self.channels
            if isinstance(c, dict)
        ]
        self.channels_hash = (
            hashlib.sha256("|".join(rows).encode("utf-8")).hexdigest() if rows else ""
        )

    def is_favorite(self, url: str) -> bool:
        return url in self.favorites

    def reset(self):
        """Reset all state to defaults (for testing)."""
        self.is_loading = False
        self.is_online = True
        self.channels = []
        self.history = []
        self.favorites = []
        self.user_country = ""
        self.has_accepted_terms = False
        self.is_first_launch = True
        self.is_deep_link_launch = False
        self.channels_hash = ""
        self.update_available = False
        self.update_data = None
        self.is_premium = False


state = AppState()
