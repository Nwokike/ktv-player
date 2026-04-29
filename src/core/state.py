import flet as ft


@ft.observable
class AppState:
    current_url: str = ""
    is_loading: bool = False
    history: list[str] = []
    channels: list[dict] = []
    categorized_channels: dict[str, list[dict]] = {}
    country_channels: dict[str, list[dict]] = {}
    favorites: list[str] = []
    current_view: str = "/"

    # Onboarding & Legal
    user_country: str = ""
    has_accepted_terms: bool = False
    is_first_launch: bool = True
    theme_mode: ft.ThemeMode = ft.ThemeMode.SYSTEM

    def __init__(self):
        self.history = []
        self.channels = []
        self.favorites = []
        self.categorized_channels = {}
        self.country_channels = {}

    def add_to_history(self, url: str):
        if url in self.history:
            self.history.remove(url)
        self.history.insert(0, url)
        if len(self.history) > 20:
            self.history = self.history[:20]


# Single instance for the application
state = AppState()
