"""VideoCard — single local video tile for folder expansion grid."""

from collections.abc import Callable

import flet as ft
from flet import Control

from app_next.components.focus_styles import card_button_style
from services.local_scanner import LocalVideo


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def VideoCard(
    video: LocalVideo,
    on_play: Callable[[str], None],
) -> Control:
    return ft.FilledButton(
        height=140,
        on_click=lambda e: on_play(video.path),
        style=card_button_style(padding=ft.Padding.all(12), radius=16),
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
