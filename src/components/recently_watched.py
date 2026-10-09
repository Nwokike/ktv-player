"""RecentlyWatched — horizontal scrolling carousel of last 10 watched streams."""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.focus_styles import card_button_style
from core.constants import LBL_RECENTLY_WATCHED
from core.theme import AppColors
from utils.history import resolve_entry


def RecentlyWatched(
    history: list[dict | str],
    channels_map: dict[str, dict],
    on_play: Callable[..., None],
    on_view_all: Callable[[], None] | None = None,
) -> Control:
    visible_items = history or []
    visible_items = visible_items[:10]

    if not visible_items:
        return ft.Container(height=0, visible=False)

    cards = []
    for entry in visible_items:
        resolved = resolve_entry(entry, channels_map)
        if resolved is None:
            continue
        url, stored_title, title, logo_src = resolved

        cards.append(
            ft.FilledButton(
                on_click=lambda e, u=url, t=stored_title: on_play(u, t),
                style=card_button_style(padding=ft.Padding.all(8), radius=10),
                content=ft.Column(
                    controls=[
                        ft.Image(
                            src=logo_src,
                            width=52,
                            height=52,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=8,
                            placeholder_src="/icon.png",
                            error_content=ft.Icon(ft.Icons.TV, size=24),
                        ),
                        ft.Text(
                            title,
                            size=11,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            width=72,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    spacing=2,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
        )

    # Header row: title on left, ink-enabled arrow on right
    header_controls: list[Control] = [
        ft.Text(
            LBL_RECENTLY_WATCHED,
            size=15,
            weight=ft.FontWeight.W_600,
            color=AppColors.grey_dim(),
        ),
    ]
    if callable(on_view_all):
        header_controls.append(ft.Container(expand=True))
        header_controls.append(
            ft.Container(
                content=ft.Icon(
                    ft.Icons.ARROW_FORWARD_ROUNDED,
                    size=18,
                    color=AppColors.grey_dim(),
                ),
                padding=6,
                border_radius=8,
                ink=True,
                tooltip="View all",
                on_click=lambda e: on_view_all(),
            )
        )

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=header_controls,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ListView(
                    controls=cards,
                    horizontal=True,
                    height=90,
                    spacing=8,
                    build_controls_on_demand=True,
                ),
            ],
            spacing=6,
        ),
        padding=ft.Padding(12, 4, 12, 4),
    )
