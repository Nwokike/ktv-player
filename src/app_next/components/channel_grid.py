"""ChannelGrid — single flat virtualized GridView with ad insertion.

Legacy pagination (show_prev/show_next) is removed. GridView's
build_controls_on_demand=True lazy-mounts off-screen items. Cards are
keyed by URL for stable identity across filter changes.
"""

from collections.abc import Callable
from typing import Any

import flet as ft
from flet.controls.control import Control

from app_next.components.channel_card import ChannelCard
from app_next.components.empty_state import EmptyState
from core.constants import CHANNEL_CARD_AD_INTERVAL
from services.liveliness import liveliness_cache


def ChannelGrid(
    channels: list[dict],
    favorites_set: set[str],
    on_play: Callable[[str], None],
    on_toggle_favorite: Callable[[str], None],
    liveliness_cache_obj: Any = None,
    ad_service: Any = None,
) -> Control:
    _liveliness = liveliness_cache_obj or liveliness_cache

    controls: list[Control] = []

    for idx, ch in enumerate(channels):
        url = ch.get("url", "")

        card = ChannelCard(
            channel=ch,
            is_favorite=url in favorites_set,
            on_play=on_play,
            on_toggle_favorite=on_toggle_favorite,
            liveliness_status=_liveliness.get(url)
            if hasattr(_liveliness, "get")
            else None,
        )

        controls.append(
            ft.Container(
                content=card, col={"xs": 4, "sm": 3, "md": 2, "lg": 2}, padding=4
            )
        )

        if ad_service and (idx + 1) % CHANNEL_CARD_AD_INTERVAL == 0:
            ad_slot = (
                ad_service.get_standard_banner_ad()
                if hasattr(ad_service, "get_standard_banner_ad")
                else None
            )
            if ad_slot:
                controls.append(
                    ft.Container(
                        content=ad_slot,
                        col=12,
                        alignment=ft.Alignment.CENTER,
                        padding=ft.Padding(0, 5, 0, 5),
                    )
                )
            else:
                controls.append(ft.Container(col=12, height=20))

    if not controls:
        return EmptyState(
            title="No channels found",
            message="Adjust filters or add content.",
            action_label=None,
        )

    return ft.GridView(
        controls=controls,
        expand=True,
        runs_count=3,
        max_extent=160,
        child_aspect_ratio=0.75,
        spacing=12,
        run_spacing=12,
        padding=ft.Padding(8, 4, 8, 4),
        cache_extent=600,
        build_controls_on_demand=True,
    )
