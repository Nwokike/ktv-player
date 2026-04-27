import flet as ft
from components.player.immersive_player import ImmersivePlayer
from core.theme import AppColors

class PlayerView(ft.Container):
    def __init__(self, url: str, on_back: callable):
        super().__init__()
        self.url = url
        self.on_back = on_back
        self.expand = True
        self.bgcolor = ft.Colors.BLACK
        
        self.content = ImmersivePlayer(
            resource=self.url,
            on_close=self.on_back
        )
