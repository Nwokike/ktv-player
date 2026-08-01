"""ChannelGrid — paginated grid with interleaved banner ads."""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.channel_card import ChannelCard
from components.empty_state import EmptyState
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
        col={"xs": 6, "sm": 4, "md": 3, "lg": 2, "xl": 2},
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

    def _seed_page_liveliness():
        if visible:
            from services.liveliness_checker import (
                drain_queue,
                enqueue_liveliness_check,
            )
            from services.logo_cache import enqueue_logo_download

            drain_queue()
            for ch in visible:
                url = ch.get("url", "")
                if url:
                    enqueue_liveliness_check(url)
                logo = ch.get("logo") or ""
                if logo and not logo.startswith("/"):
                    enqueue_logo_download(logo)

    ft.use_effect(_seed_page_liveliness, [current_page, len(channels)])

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
            ft.ResponsiveRow(
                controls=grid_controls,
                spacing=12,
                run_spacing=12,
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

    if total_pages > 1:
        from core.theme import AppColors

        prev_disabled = current_page == 0
        next_disabled = current_page >= total_pages - 1

        prev_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                        size=14,
                        color=AppColors.grey_dim()
                        if prev_disabled
                        else AppColors.PRIMARY,
                    ),
                    ft.Text(
                        "Previous",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=AppColors.grey_dim()
                        if prev_disabled
                        else AppColors.PRIMARY,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding(14, 8, 14, 8),
            border_radius=10,
            border=ft.Border.all(
                1.5,
                AppColors.grey_dim() if prev_disabled else AppColors.PRIMARY,
            ),
            bgcolor=ft.Colors.with_opacity(0.05, AppColors.PRIMARY)
            if not prev_disabled
            else ft.Colors.TRANSPARENT,
            ink=not prev_disabled,
            on_click=lambda e: (
                set_current_page(max(0, current_page - 1))
                if not prev_disabled
                else None
            ),
        )

        next_btn = ft.Container(
            content=ft.Row(
                [
                    ft.Text(
                        "Next",
                        size=12,
                        weight=ft.FontWeight.BOLD,
                        color=AppColors.grey_dim()
                        if next_disabled
                        else AppColors.PRIMARY,
                    ),
                    ft.Icon(
                        ft.Icons.ARROW_FORWARD_IOS_ROUNDED,
                        size=14,
                        color=AppColors.grey_dim()
                        if next_disabled
                        else AppColors.PRIMARY,
                    ),
                ],
                spacing=6,
            ),
            padding=ft.Padding(14, 8, 14, 8),
            border_radius=10,
            border=ft.Border.all(
                1.5,
                AppColors.grey_dim() if next_disabled else AppColors.PRIMARY,
            ),
            bgcolor=ft.Colors.with_opacity(0.05, AppColors.PRIMARY)
            if not next_disabled
            else ft.Colors.TRANSPARENT,
            ink=not next_disabled,
            on_click=lambda e: (
                set_current_page(min(total_pages - 1, current_page + 1))
                if not next_disabled
                else None
            ),
        )

        from flet import context

        from components.banner_ad import build_banner_ad

        page = context.page
        bot_ad = build_banner_ad(page)
        if bot_ad:
            sections.append(bot_ad)

        sections.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        prev_btn,
                        ft.Text(
                            f"Page {current_page + 1} of {total_pages}  ·  {len(channels)} channels",
                            size=12,
                            weight=ft.FontWeight.W_500,
                            color=ft.Colors.with_opacity(0.8, ft.Colors.ON_SURFACE),
                        ),
                        next_btn,
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
