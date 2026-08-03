"""RecentlyWatchedScreen — full vertical list of all watched streams."""

import flet as ft
from flet import Control

from core.constants import LBL_RECENTLY_WATCHED
from core.theme import AppColors
from services.logo_cache import get_cached_logo


def _display_name(url: str) -> str:
    import os

    name = os.path.splitext(os.path.basename(url))[0]
    return name if name else "Stream"


def RecentlyWatchedScreen(
    history: list[str],
    channels_map: dict[str, dict],
    on_play,
) -> Control:
    """Full-screen view of all history items."""

    def _make_card(url: str) -> Control:
        ch = channels_map.get(url, {"name": _display_name(url), "logo": ""})
        logo_src = ch.get("logo", "") or "/icon.png"
        if not logo_src.startswith("/"):
            cached = get_cached_logo(logo_src)
            if cached:
                logo_src = cached

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Image(
                        src=logo_src,
                        width=48,
                        height=48,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=8,
                        error_content=ft.Icon(ft.Icons.TV, size=22),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                ch.get("name", "Stream"),
                                size=13,
                                weight=ft.FontWeight.W_500,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Text(
                                url if url.startswith("/") else url[:60],
                                size=10,
                                color=AppColors.grey_dim(),
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(8, 8, 8, 8),
            border_radius=10,
            on_click=lambda e, u=url: on_play(u),
            ink=True,
        )

    if not history:
        body = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                controls=[
                    ft.Icon(ft.Icons.HISTORY, size=48, color=AppColors.grey_dim()),
                    ft.Text(
                        "No watch history yet", size=14, color=AppColors.grey_dim()
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
        )
    else:
        cards = [_make_card(url) for url in history]
        body = ft.ListView(
            controls=cards,
            expand=True,
            spacing=4,
            padding=ft.Padding(16, 8, 16, 16),
        )

    from components.banner_ad import build_banner_ad

    page_obj = ft.context.page
    rw_banner = build_banner_ad(page_obj)

    controls = [
        ft.AppBar(
            title=ft.Text(LBL_RECENTLY_WATCHED, weight=ft.FontWeight.BOLD),
            center_title=False,
        ),
    ]
    if rw_banner:
        controls.append(rw_banner)
    controls.append(body)

    return ft.Column(
        controls=controls,
        expand=True,
        spacing=0,
    )
