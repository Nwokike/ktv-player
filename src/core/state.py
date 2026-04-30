import flet as ft


@ft.observable
class AppState:
    is_loading: bool = False
    history: list[str] = []
    channels: list[dict] = []
    favorites: list[str] = []

    user_country: str = ""
    has_accepted_terms: bool = False
    is_first_launch: bool = True
    theme_mode: ft.ThemeMode = ft.ThemeMode.SYSTEM

    def __init__(self):
        self.history = []
        self.channels = []
        self.favorites = []

    def add_to_history(self, url: str):
        if url in self.history:
            self.history.remove(url)
        self.history.insert(0, url)
        if len(self.history) > 20:
            self.history = self.history[:20]


state = AppState()
