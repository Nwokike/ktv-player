"""ChannelGrid — paginated grid with interleaved banner ads."""

from collections.abc import Callable

import flet as ft
from flet import Control

from app_next.components.channel_card import ChannelCard
from app_next.components.empty_state import EmptyState
from core.constants import AD_ROW_INTERVAL, PAGE_SIZE

# Grid layout
_RUNS_COUNT = 3
_MAX_EXTENT = 160
_CHILD_ASPECT = 0.75
_SPACING = 12
_RUN_SPACING = 12


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
    current_page, set_current_page = ft.use_state(0)

    total_pages = max(1, (len(channels) + PAGE_SIZE - 1) // PAGE_SIZE)
    # Clamp page if channels changed (filter switched)
    if current_page >= total_pages:
        current_page = total_pages - 1

    start = current_page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(channels))
    visible = channels[start:end]

    if not visible:
        return EmptyState(
            title="No channels found",
            message="Adjust filters or add content.",
            action_label=None,
        )

    # Build grid sections with ads between chunks
    sections: list[Control] = []
    for chunk_start in range(0, len(visible), AD_ROW_INTERVAL):
        chunk = visible[chunk_start : chunk_start + AD_ROW_INTERVAL]

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

        # Ad after this chunk (except after the last)
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

    # Pagination controls
    sections.append(
        ft.Container(
            content=ft.Row(
                controls=[
                    ft.OutlinedButton(
                        content=ft.Text("← Previous"),
                        icon=ft.Icons.CHEVRON_LEFT,
                        on_click=lambda e: set_current_page(max(0, current_page - 1)),
                        disabled=current_page == 0,
                    ),
                    ft.Text(
                        f"Page {current_page + 1} of {total_pages}  ·  {len(channels)} channels",
                        size=12,
                        color=ft.Colors.with_opacity(0.6, ft.Colors.ON_SURFACE),
                    ),
                    ft.OutlinedButton(
                        content=ft.Text("Next →"),
                        on_click=lambda e: set_current_page(
                            min(total_pages - 1, current_page + 1)
                        ),
                        disabled=current_page >= total_pages - 1,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=16,
            ),
            padding=ft.Padding(0, 16, 0, 24),
        )
    )

    return ft.Column(
        controls=sections,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
