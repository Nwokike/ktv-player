import flet as ft

from core.constants import MAX_HISTORY_ITEMS


@ft.observable
class AppState:
    is_loading: bool = False
    channels: list[dict] = []  # noqa: RUF012
    history: list[str] = []  # noqa: RUF012
    favorites: set[str] = set()  # noqa: RUF012

    user_country: str = ""
    has_accepted_terms: bool = False
    is_first_launch: bool = True
    theme_mode: ft.ThemeMode = ft.ThemeMode.SYSTEM

    channels_hash: int = 0

    def __init__(self):
        self.channels = []
        self.history = []
        self.favorites = set()

    def add_to_history(self, url: str):
        if url in self.history:
            self.history.remove(url)
        self.history.insert(0, url)
        if len(self.history) > MAX_HISTORY_ITEMS:
            self.history = self.history[:MAX_HISTORY_ITEMS]

    def set_channels(self, channels: list[dict]):
        self.channels = channels
        self.channels_hash = sum(hash(c.get("url", "")) for c in channels) % 10_000_000

    def is_favorite(self, url: str) -> bool:
        return url in self.favorites

    def reset(self):
        """Reset all state to defaults (for testing)."""
        self.is_loading = False
        self.channels = []
        self.history = []
        self.favorites = set()
        self.user_country = ""
        self.has_accepted_terms = False
        self.is_first_launch = True
        self.theme_mode = ft.ThemeMode.SYSTEM
        self.channels_hash = 0


state = AppState()
