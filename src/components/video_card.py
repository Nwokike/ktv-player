"""VideoCard — single local video tile for folder expansion grid."""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.focus_styles import attach_focus_pop, card_button_style
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


def _preview(video: LocalVideo) -> Control:
    """Frame preview when a thumbnail exists, movie icon otherwise."""
    fallback = ft.Icon(
        ft.Icons.MOVIE_CREATION_OUTLINED, size=36, color=ft.Colors.PRIMARY
    )
    if not video.thumbnail:
        return fallback
    return ft.Image(
        src=video.thumbnail,
        height=64,
        fit=ft.BoxFit.COVER,
        border_radius=10,
        error_content=fallback,
    )


def VideoCard(
    video: LocalVideo,
    on_play: Callable[[str], None],
    on_long_press: Callable[[LocalVideo], None] | None = None,
    on_menu: Callable[[LocalVideo], None] | None = None,
) -> Control:
    """Local video tile.

    When `on_long_press` is given the card becomes long-pressable (MX Player
    style) — the folder screen uses it for the Play/Delete menu.
    """
    button = attach_focus_pop(
        ft.FilledButton(
            height=140,
            on_click=lambda e: on_play(video.path),
            style=card_button_style(padding=ft.Padding.all(12), radius=16),
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.MOVIE, size=18, color=ft.Colors.GREY),
                        ],
                    ),
                    _preview(video),
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
    )

    card: Control = button
    if on_menu is not None:
        # The options button is a SIBLING of the play button, not nested
        # inside it: a button inside a button makes it ambiguous which one
        # a tap (or D-pad OK) activates. Long-press remains available on
        # phones, but the TV remote has no long-press at all.
        card = ft.Container(
            content=ft.Stack(
                controls=[
                    button,
                    ft.Container(
                        content=ft.IconButton(
                            icon=ft.Icons.MORE_VERT,
                            icon_size=16,
                            tooltip="Options",
                            on_click=lambda e, v=video: on_menu(v),
                        ),
                        alignment=ft.Alignment.TOP_RIGHT,
                        padding=ft.Padding.only(top=2, right=2),
                    ),
                ],
            ),
        )

    if on_long_press is None:
        return card
    return ft.GestureDetector(
        content=card,
        on_long_press=lambda e: on_long_press(video),
    )
