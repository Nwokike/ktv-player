"""ChannelCard — single clickable tile in the virtualized grid.

Pure (prefers props over state). Identity key = `ft.ValueKey(channel["url"])`
so GridView reconciliation preserves focus/animations across filter changes.

Favorites: `is_favorite` is passed as a prop (computed in HomeScreen via a
memoized set-lookup). The card does NOT read `state.favorites` directly.

Liveliness: `liveliness_status` prop (True/False/None). Card calls
`enqueue_logo_download(logo_src)` on render (fire-and-forget, same as legacy).
"""

from collections.abc import Callable

import flet as ft
from flet.controls.control import Control

from core.constants import (
    CARD_BORDER_RADIUS,
    CARD_HEIGHT,
    LOGO_BORDER_RADIUS,
    LOGO_SIZE,
    STATUS_DOT_SIZE,
)
from core.theme import AppColors
from services.logo_cache import enqueue_logo_download, get_cached_logo


def ChannelCard(
    channel: dict,
    is_favorite: bool,
    on_play: Callable[[str], None],
    on_toggle_favorite: Callable[[str], None],
    liveliness_status: bool | None = None,
) -> Control:
    url = channel.get("url", "")
    name = channel.get("name", "Unknown")
    logo_src = channel.get("logo") or "/icon.png"

    # resolve logo source
    if logo_src.startswith("/"):
        resolved_logo = logo_src
    else:
        cached = get_cached_logo(logo_src)
        if cached:
            resolved_logo = cached
        else:
            resolved_logo = logo_src
            enqueue_logo_download(logo_src)  # fire-and-forget

    # liveliness dot
    if liveliness_status is True:
        dot_color = AppColors.SUCCESS
    elif liveliness_status is False:
        dot_color = AppColors.ERROR
    else:
        dot_color = AppColors.GREY_DIM

    fav_icon = ft.Icon(
        ft.Icons.FAVORITE if is_favorite else ft.Icons.FAVORITE_BORDER,
        size=16,
        color=AppColors.PRIMARY if is_favorite else ft.Colors.WHITE_70,
    )

    return ft.Container(
        key=ft.ValueKey(url),
        height=CARD_HEIGHT,
        padding=12,
        border_radius=CARD_BORDER_RADIUS,
        ink=True,
        on_click=lambda e: on_play(url) if on_play else None,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=fav_icon,
                            on_click=lambda e, u=url: on_toggle_favorite(u),
                            tooltip="Favorite",
                        ),
                        ft.Container(
                            width=STATUS_DOT_SIZE,
                            height=STATUS_DOT_SIZE,
                            border_radius=STATUS_DOT_SIZE // 2,
                            bgcolor=dot_color,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Image(
                    src=resolved_logo,
                    width=LOGO_SIZE,
                    height=LOGO_SIZE,
                    fit=ft.BoxFit.CONTAIN,
                    border_radius=LOGO_BORDER_RADIUS,
                    error_content=ft.Icon(ft.Icons.TV, size=30),
                ),
                ft.Text(
                    name,
                    size=12,
                    weight=ft.FontWeight.W_500,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
    )
