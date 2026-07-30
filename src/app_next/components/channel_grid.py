"""ChannelGrid — paginated grid with interleaved banner ads."""

from collections.abc import Callable

import flet as ft
from flet import Control

from app_next.components.channel_card import ChannelCard
from app_next.components.empty_state import EmptyState
from core.constants import AD_ROW_INTERVAL, LOAD_MORE_SIZE, PAGE_SIZE

# Grid layout
_RUNS_COUNT = 3
_MAX_EXTENT = 160
_CHILD_ASPECT = 0.75
_SPACING = 12
_RUN_SPACING = 12
_ROW_HEIGHT = int(_MAX_EXTENT * _CHILD_ASPECT) + _RUN_SPACING


def _build_channel_card(ch, favorites_set, on_play, on_toggle_favorite):
    """Build a single channel card control."""
    from services.liveliness import liveliness_cache

    url = ch.get("url", "")
    return ft.Container(
        content=ChannelCard(
            channel=ch,
            is_favorite=url in favorites_set,
            on_play=on_play,
            on_toggle_favorite=on_toggle_favorite,
            liveliness_status=liveliness_cache.get(url),
        ),
        col={"xs": 4, "sm": 3, "md": 2, "lg": 2},
        padding=4,
    )


@ft.component
def ChannelGrid(
    channels: list[dict],
    favorites_set: set[str],
    on_play: Callable[[str], None],
    on_toggle_favorite: Callable[[str], None],
    ad_service=None,
) -> Control:
    displayed_count, set_displayed_count = ft.use_state(PAGE_SIZE)
    has_more = displayed_count < len(channels)

    def _on_scroll(e):
        if not has_more:
            return
        remaining = e.extent_after if hasattr(e, "extent_after") else 0
        if remaining < 200:
            new_count = min(displayed_count + LOAD_MORE_SIZE, len(channels))
            if new_count != displayed_count:
                set_displayed_count(new_count)

    def _load_more(e=None):
        new_count = min(displayed_count + LOAD_MORE_SIZE, len(channels))
        set_displayed_count(new_count)

    visible = channels[:displayed_count]

    if not visible:
        return EmptyState(
            title="No channels found",
            message="Adjust filters or add content.",
            action_label=None,
        )

    # Build sections: groups of AD_ROW_INTERVAL channels, with ad between groups
    sections: list[Control] = []
    for chunk_start in range(0, len(visible), AD_ROW_INTERVAL):
        chunk = visible[chunk_start : chunk_start + AD_ROW_INTERVAL]

        # Build grid for this chunk
        grid_controls = [
            _build_channel_card(ch, favorites_set, on_play, on_toggle_favorite)
            for ch in chunk
        ]
        sections.append(
            ft.GridView(
                controls=grid_controls,
                expand=True,
                runs_count=_RUNS_COUNT,
                max_extent=_MAX_EXTENT,
                child_aspect_ratio=_CHILD_ASPECT,
                spacing=_SPACING,
                run_spacing=_RUN_SPACING,
                padding=ft.Padding(8, 0, 8, 0),
                cache_extent=600,
                build_controls_on_demand=True,
            )
        )

        # Ad after this chunk (except after the last chunk)
        if chunk_start + AD_ROW_INTERVAL < len(visible) and ad_service:
            ad_slot = (
                ad_service.get_standard_banner_ad()
                if hasattr(ad_service, "get_standard_banner_ad")
                else None
            )
            if ad_slot:
                sections.append(ad_slot)
            else:
                sections.append(ft.Container(height=12))

    # "Load More" button
    if has_more:
        remaining = len(channels) - displayed_count
        sections.append(
            ft.Container(
                content=ft.FilledButton(
                    content=ft.Text(f"Load More ({remaining} remaining)", size=13),
                    icon=ft.Icons.ARROW_DOWNWARD_ROUNDED,
                    on_click=_load_more,
                ),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding(0, 12, 0, 12),
            )
        )

    return ft.Column(
        controls=sections,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        on_scroll=_on_scroll,
    )
