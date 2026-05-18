import flet as ft

from core.constants import MAX_HISTORY_ITEMS


@ft.observable
class AppState:
    is_loading: bool = False
    history: list[str] = []  # noqa: RUF012
    channels: list[dict] = []  # noqa: RUF012
    favorites: list[str] = []  # noqa: RUF012

    user_country: str = ""
    has_accepted_terms: bool = False
    is_first_launch: bool = True
    theme_mode: ft.ThemeMode = ft.ThemeMode.SYSTEM

    def add_to_history(self, url: str):
        if url in self.history:
            self.history.remove(url)
        self.history.insert(0, url)
        if len(self.history) > MAX_HISTORY_ITEMS:
            self.history = self.history[:MAX_HISTORY_ITEMS]

    def get_recent_history(self, limit: int = 10) -> list[str]:
        return list(self.history[:limit])


state = AppState()
