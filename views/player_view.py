import flet as ft
from components.player.immersive_player import ImmersivePlayer
from core.theme import AppColors

@ft.component
def PlayerView(url: str, on_back: callable):
    return ft.Container(
        content=ImmersivePlayer(
            resource=url,
            on_close=on_back
        ),
        bgcolor=ft.Colors.BLACK,
        expand=True,
    )
