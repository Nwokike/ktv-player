"""ChannelGrid — paginated GridView with ad insertion and viewport-driven liveliness."""

from collections.abc import Callable

import flet as ft
from flet import Control

from app_next.components.channel_card import ChannelCard
from app_next.components.empty_state import EmptyState
from core.constants import AD_ROW_INTERVAL, LOAD_MORE_SIZE, PAGE_SIZE

# Grid layout constants
_RUNS_COUNT = 3
_MAX_EXTENT = 160
_CHILD_ASPECT = 0.75
_SPACING = 12
_RUN_SPACING = 12
_ROW_HEIGHT = int(_MAX_EXTENT * _CHILD_ASPECT) + _RUN_SPACING
_BUFFER_ROWS = 5


def _build_controls(
    channels: list[dict],
    displayed_count: int,
    favorites_set: set[str],
    on_play: Callable[[str], None],
    on_toggle_favorite: Callable[[str], None],
    ad_service,
) -> list[Control]:
    """Build the flat controls list with ads interleaved every AD_ROW_INTERVAL items."""
    from services.liveliness import liveliness_cache

    visible = channels[:displayed_count]
    controls: list[Control] = []

    for idx, ch in enumerate(visible):
        url = ch.get("url", "")

        card = ChannelCard(
            channel=ch,
            is_favorite=url in favorites_set,
            on_play=on_play,
            on_toggle_favorite=on_toggle_favorite,
            liveliness_status=liveliness_cache.get(url),
        )

        controls.append(
            ft.Container(
                content=card, col={"xs": 4, "sm": 3, "md": 2, "lg": 2}, padding=4
            )
        )

        # Ad every AD_ROW_INTERVAL items
        if ad_service and (idx + 1) % AD_ROW_INTERVAL == 0:
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

    return controls


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
        """Auto-load more when near bottom."""
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

    controls = _build_controls(channels, displayed_count, favorites_set, on_play, on_toggle_favorite, ad_service)

    # "Load More" button at bottom
    if has_more:
        remaining = len(channels) - displayed_count
        controls.append(
            ft.Container(
                content=ft.FilledButton(
                    content=ft.Text(f"Load More ({remaining} remaining)", size=13),
                    icon=ft.Icons.ARROW_DOWNWARD_ROUNDED,
                    on_click=_load_more,
                ),
                        alignment=ft.Alignment.CENTER,
                padding=ft.Padding(0, 12, 0, 12),
                col=12,
            )
        )

    if not controls:
        return EmptyState(
            title="No channels found",
            message="Adjust filters or add content.",
            action_label=None,
        )

    return ft.GridView(
        controls=controls,
        expand=True,
        runs_count=_RUNS_COUNT,
        max_extent=_MAX_EXTENT,
        child_aspect_ratio=_CHILD_ASPECT,
        spacing=_SPACING,
        run_spacing=_RUN_SPACING,
        padding=ft.Padding(8, 4, 8, 4),
        cache_extent=600,
        build_controls_on_demand=True,
        on_scroll=_on_scroll,
    )
