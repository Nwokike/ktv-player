from dataclasses import field

import flet as ft

from core.constants import MAX_HISTORY_ITEMS


@ft.observable
class AppState:
    is_loading: bool = False
    is_online: bool = True
    channels: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    favorites: list[str] = field(default_factory=list)

    user_country: str = ""
    has_accepted_terms: bool = False
    is_first_launch: bool = True
    theme_mode: ft.ThemeMode = ft.ThemeMode.SYSTEM
    is_deep_link_launch: bool = False

    channels_hash: int = 0

    # Update service (version dialog reads these; None/False = up to date)
    update_available: bool = False
    update_data: dict | None = None

    def __init__(self):
        self.channels = []
        self.history = []
        self.favorites = []

    def add_to_history(self, url: str, title: str = ""):
        # Normalize: store as dict with url and title, carrying forward any saved position/duration
        existing = next((e for e in self.history if e.get("url") == url), None)
        entry: dict = {"url": url, "title": title or url}
        if isinstance(existing, dict):
            if existing.get("position") is not None:
                entry["position"] = existing["position"]
            if existing.get("duration") is not None:
                entry["duration"] = existing["duration"]
        # Remove existing entry with same URL
        self.history = [e for e in self.history if e.get("url") != url]
        self.history.insert(0, entry)
        if len(self.history) > MAX_HISTORY_ITEMS:
            self.history = self.history[:MAX_HISTORY_ITEMS]

    def set_channels(self, channels: list[dict]):
        self.channels = list(channels)  # copy, not direct reference
        self.channels_hash = (
            sum(hash(c.get("url", "")) for c in self.channels) % 10_000_000
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
        self.theme_mode = ft.ThemeMode.SYSTEM
        self.channels_hash = 0
        self.update_available = False
        self.update_data = None


state = AppState()
