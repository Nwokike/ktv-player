"""ChannelCard — sleek container-based TV card with micro-zoom D-pad focus."""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.focus_styles import card_button_style, card_focus_scale
from core.constants import (
    CARD_BORDER_RADIUS,
    CARD_HEIGHT,
    LOGO_BORDER_RADIUS,
    LOGO_SIZE,
    STATUS_DOT_SIZE,
)
from core.theme import AppColors
from services.logo_cache import get_cached_logo


@ft.component
def LivelinessChannelCard(
    channel: dict,
    is_favorite: bool,
    on_play: Callable[..., None],
    on_toggle_favorite: Callable[[str], None],
) -> Control:
    """Per-card liveliness subscription wrapper.

    Each visible card subscribes to the liveliness cache for ITS url, so a
    verdict rebuilds exactly one card instead of the whole grid (the old
    page-level subscription re-created all 24 cards per tick). The plain
    ChannelCard below stays a plain function — the subscription lives here
    where hooks are allowed.
    """
    url = channel.get("url", "")
    from services.liveliness import liveliness_cache

    status, set_status = ft.use_state(
        lambda: liveliness_cache.get(url) if url else None
    )

    def _on_change(changed_url=None):
        # None means "bulk clear": re-read unconditionally.
        if changed_url is None or changed_url == url:
            set_status(liveliness_cache.get(url) if url else None)

    def _subscribe():
        if url:
            liveliness_cache.add_on_change(_on_change)

    def _unsubscribe():
        if url:
            liveliness_cache.remove_on_change(_on_change)

    # NOTE: cleanup is the 3rd use_effect arg (installed
    # flet/components/hooks/use_effect.py) — NOT a setup return value.
    ft.use_effect(_subscribe, [], _unsubscribe)

    return ChannelCard(
        channel=channel,
        is_favorite=is_favorite,
        on_play=on_play,
        on_toggle_favorite=on_toggle_favorite,
        liveliness_status=status,
    )


def ChannelCard(
    channel: dict,
    is_favorite: bool,
    on_play: Callable[..., None],
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

    fav_icon_name = (
        ft.Icons.STAR_ROUNDED if is_favorite else ft.Icons.STAR_BORDER_ROUNDED
    )
    fav_icon_color = AppColors.PRIMARY if is_favorite else AppColors.grey_dim()

    top_row = ft.Row(
        controls=[
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
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    logo_widget = ft.Image(
        src=resolved_logo,
        width=LOGO_SIZE,
        height=LOGO_SIZE,
        fit=ft.BoxFit.CONTAIN,
        border_radius=LOGO_BORDER_RADIUS,
        placeholder_src="/icon.png",
        error_content=ft.Icon(ft.Icons.TV, size=30),
    )

    title_widget = ft.Text(
        name,
        size=11,
        weight=ft.FontWeight.W_500,
        text_align=ft.TextAlign.CENTER,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    button = ft.FilledButton(
        key=ft.ValueKey(url),
        height=CARD_HEIGHT,
        content=ft.Column(
            controls=[
                top_row,
                logo_widget,
                title_widget,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        ),
        on_click=lambda e: on_play(url),
        style=card_button_style(
            padding=ft.Padding.symmetric(horizontal=10, vertical=8),
            radius=CARD_BORDER_RADIUS,
        ),
        # Declarative scale cue: the FOCUSED border is the primary cue;
        # the animation interpolates the focus/blur scale below instead
        # of snapping. (The old attach_focus_pop mutated frozen controls
        # and never visibly applied — deleted.)
        animate_scale=card_focus_scale(),
    )
    button.on_focus = lambda e: setattr(button, "scale", 1.04)
    button.on_blur = lambda e: setattr(button, "scale", 1.0)
    return button
