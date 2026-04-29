import flet as ft
from components.player.immersive_player import ImmersivePlayer


def build_player_view(url: str, on_back: callable) -> ft.View:
    """Builds the player view."""

    player = ImmersivePlayer(resource=url, on_close=on_back)

    return ft.View(
        route=f"/play?url={url}",
        controls=[
            ft.Container(
                content=player,
                expand=True,
                bgcolor=ft.Colors.BLACK,
            )
        ],
        padding=0,
    )
