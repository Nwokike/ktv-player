"""RecentlyWatched — horizontal scrolling carousel of last 10 watched streams."""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.focus_styles import card_button_style
from core.constants import LBL_RECENTLY_WATCHED
from core.theme import AppColors
from services.logo_cache import get_cached_logo


def _display_name(url: str) -> str:
    import os

    name = os.path.splitext(os.path.basename(url))[0]
    return name if name else "Stream"


def RecentlyWatched(
    history: list[dict],
    channels_map: dict[str, dict],
    on_play: Callable[[str], None],
    on_view_all: Callable[[], None] | None = None,
) -> Control:
    visible_items = history[:10]

    if not visible_items:
        return ft.Container(height=0, visible=False)

    cards = []
    for entry in visible_items:
        url = entry.get("url", "")
        # Use stored title, fall back to channels_map, then _display_name
        if isinstance(entry, dict):
            title = (
                entry.get("title")
                or channels_map.get(url, {}).get("name")
                or _display_name(url)
            )
            logo = channels_map.get(url, {}).get("logo", "") or entry.get("logo", "")
        else:
            # Legacy string entry
            title = channels_map.get(url, {}).get("name") or _display_name(url)
            logo = channels_map.get(url, {}).get("logo", "")

        logo_src = logo or "/icon.png"
        if not logo_src.startswith("/"):
            cached = get_cached_logo(logo_src)
            if cached:
                logo_src = cached

        cards.append(
            ft.FilledButton(
                on_click=lambda e, u=url: on_play(u),
                style=card_button_style(padding=ft.Padding.all(8), radius=10),
                content=ft.Column(
                    controls=[
                        ft.Image(
                            src=logo_src,
                            width=52,
                            height=52,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=8,
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
