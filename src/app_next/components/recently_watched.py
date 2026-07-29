"""RecentlyWatched — horizontal scrolling carousel of last 10 watched streams.

Plain function (no @ft.component needed). Uses horizontal ListView with
build_controls_on_demand. Hidden when history is empty.

Each card is an `ft.FilledButton` (NOT a `Container`) so that Flet 0.86.4
will give it native D-pad focus on Android TV / Fire Stick remotes — see
Phase A of the focus rewrite. A `card_button_style` keeps the prior
visuals (8px padding, 10px corner radius, ink/splash on press).
"""

from collections.abc import Callable

import flet as ft
from flet.controls.control import Control

from app_next.components.focus_styles import card_button_style
from core.constants import LBL_RECENTLY_WATCHED
from core.theme import AppColors
from services.logo_cache import get_cached_logo


def RecentlyWatched(
    history: list[str],
    channels_map: dict[str, dict],
    on_play: Callable[[str], None],
) -> Control:
    visible_items = history[:10]

    if not visible_items:
        return ft.Container(height=0, visible=False)

    cards = []
    for url in visible_items:
        ch = channels_map.get(url, {"name": url, "logo": ""})
        logo_src = ch.get("logo", "") or "/icon.png"
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
                            ch.get("name", "Stream"),
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

    return ft.Container(
        content=ft.Column(
            controls=[
                ft.Text(
                    LBL_RECENTLY_WATCHED,
                    size=15,
                    weight=ft.FontWeight.W_600,
                    color=AppColors.grey_dim(),
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
