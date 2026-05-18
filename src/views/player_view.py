import flet as ft

from components.player.immersive_player import ImmersivePlayer


def build_player_view(page_obj: ft.Page, url: str, on_back: callable, title: str = "", player: ImmersivePlayer = None) -> ft.View:
    if player is None:
        raise ValueError("player must be provided to build_player_view")

    page_obj.run_task(player.start_playback)

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
