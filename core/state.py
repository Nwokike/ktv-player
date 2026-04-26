import flet as ft
from dataclasses import dataclass, field

@ft.observable
class AppState:
    current_url: str = ""
    is_loading: bool = False
    history: list[str] = []
    channels: list[dict] = []
    favorites: list[str] = []
    current_view: str = "/"
    
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

# Single instance for the application
state = AppState()
