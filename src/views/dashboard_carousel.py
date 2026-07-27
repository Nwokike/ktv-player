"""Recently watched horizontal carousel for dashboard."""

import flet as ft

from core.constants import LBL_RECENTLY_WATCHED
from core.state import state
from core.theme import AppColors
from services.logo_cache import get_cached_logo


def build_recently_watched_section(page_obj, on_play):
    """Build the Recently Watched horizontal carousel container."""
    recently_watched_row = ft.Row(
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )

    def refresh_carousel():
        recently_watched_row.controls.clear()
        if not state.history:
            return

        channel_map = {c["url"]: c for c in state.channels if "url" in c}
        tab_counter = 0

        for url in state.history[:10]:
            ch = channel_map.get(url)
            if not ch:
                continue

            logo_src = ch.get("logo", "/icon.png")
            cached = (
                get_cached_logo(logo_src)
                if logo_src and not logo_src.startswith("/")
                else None
            )

            tab_counter += 1
            card = ft.Container(
                content=ft.Column(
                    [
                        ft.Image(
                            src=cached or logo_src,
                            width=52,
                            height=52,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=14,
                            error_content=ft.Icon(ft.Icons.TV, size=24),
                        ),
                        ft.Text(
                            ch.get("name", "Unknown"),
                            size=11,
                            weight=ft.FontWeight.W_500,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            text_align=ft.TextAlign.CENTER,
                            width=72,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                ),
                padding=8,
                border_radius=16,
                bgcolor=AppColors.get_surface_variant(page_obj),
                ink=True,
                on_click=lambda e, u=url: page_obj.run_task(on_play, u),
            )
            card.tab_index = tab_counter
            recently_watched_row.controls.append(card)

    refresh_carousel()

    section = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Text(
                        LBL_RECENTLY_WATCHED,
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=AppColors.GREY_DIM,
                    ),
                    padding=ft.Padding(16, 8, 16, 4),
                ),
                ft.Container(
                    content=recently_watched_row,
                    padding=ft.Padding(16, 0, 16, 8),
                ),
            ],
            spacing=0,
        ),
        visible=bool(state.history),
    )

    return section, refresh_carousel
