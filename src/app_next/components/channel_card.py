"""ChannelCard — single clickable tile in the virtualized grid."""

from collections.abc import Callable

import flet as ft
from flet import Control

from app_next.components.focus_styles import card_button_style
from core.constants import (
    CARD_BORDER_RADIUS,
    CARD_HEIGHT,
    LOGO_BORDER_RADIUS,
    LOGO_SIZE,
    STATUS_DOT_SIZE,
)
from core.theme import AppColors
from services.logo_cache import get_cached_logo


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

    if logo_src.startswith("/"):
        resolved_logo = logo_src
    else:
        cached = get_cached_logo(logo_src)
        resolved_logo = cached if cached else logo_src

    # liveliness dot
    if liveliness_status is True:
        dot_color = AppColors.SUCCESS
    elif liveliness_status is False:
        dot_color = AppColors.ERROR
    else:
        dot_color = AppColors.grey_dim()

    fav_icon_name = ft.Icons.FAVORITE if is_favorite else ft.Icons.FAVORITE_BORDER
    fav_icon_color = AppColors.PRIMARY if is_favorite else AppColors.grey_dim()

    return ft.FilledButton(
        key=ft.ValueKey(url),
        height=CARD_HEIGHT,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        # Favorite toggle — its own focusable IconButton so the
                        # D-pad lands on it separately from the play-on-click card.
                        ft.IconButton(
                            icon=fav_icon_name,
                            icon_color=fav_icon_color,
                            icon_size=16,
                            tooltip="Favorite",
                            on_click=lambda e, u=url: on_toggle_favorite(u),
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
        on_click=lambda e: on_play(url),
        style=card_button_style(padding=ft.Padding.all(12), radius=CARD_BORDER_RADIUS),
    )
