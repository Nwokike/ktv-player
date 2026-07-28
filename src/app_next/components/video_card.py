"""VideoCard — single local video tile for folder expansion grid.

Plain function (no @ft.component). Receives a LocalVideo dataclass and
on_play callback. Shows name, file size, and a movie icon. Matches the
legacy local/cards.py layout.
"""

from collections.abc import Callable

import flet as ft
from flet.controls.control import Control

from services.local_scanner import LocalVideo, _format_size


def VideoCard(
    video: LocalVideo,
    on_play: Callable[[str], None],
) -> Control:
    return ft.Container(
        padding=12,
        border_radius=16,
        height=140,
        ink=True,
        on_click=lambda e: on_play(video.path),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            width=10,
                            height=10,
                            border_radius=5,
                            bgcolor=ft.Colors.GREEN_ACCENT_400,
                        ),
                        ft.Icon(ft.Icons.MOVIE, size=18, color=ft.Colors.GREY),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Icon(
                    ft.Icons.MOVIE_CREATION_OUTLINED, size=36, color=ft.Colors.PRIMARY
                ),
                ft.Text(
                    video.name,
                    size=12,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    _format_size(video.size),
                    size=10,
                    color=ft.Colors.GREY,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
    )
