"""Channel group classification and expansion tile builder."""

import contextlib
import logging

import flet as ft

from core.constants import LBL_SHOW_NEXT, LBL_SHOWING_RANGE, PAGE_SIZE
from core.state import state
from core.theme import AppColors
from views.tabs.channel_classification import (
    _build_groups,
    _search_channels,
)
from views.tabs.pagination import build_nav_btn, show_page

logger = logging.getLogger(__name__)


def _collapse_other_tiles(current_tile, active_tiles):
    for t in active_tiles:
        if t is not current_tile and t.expanded:
            t.expanded = False
            with contextlib.suppress(Exception):
                t.update()


def _handle_expansion(
    e,
    channels,
    active_tiles,
    page_obj,
    on_play,
    ad_service,
    liveliness,
):
    if str(e.data).lower() == "true":
        _collapse_other_tiles(e.control, active_tiles)
        if e.control.controls:
            e.control.update()
        else:
            show_page(e.control, channels, 0, page_obj, on_play, ad_service, liveliness)


def build_channel_groups(
    target,
    tab_index,
    page_obj,
    on_play,
    ad_service,
    liveliness,
    view_state,
    active_tiles,
    load_channels=None,
):
    """Build expansion tiles for channel groups. Used by Countries, Categories, and Custom tabs."""
    from components.ui.channel_grid import build_channel_grid

    if not state.channels and tab_index in (0, 1):
        if state.is_loading:
            target.controls.append(
                ft.Column(
                    [
                        ft.Container(height=80),
                        ft.ProgressRing(
                            width=60, height=60, stroke_width=6, color=AppColors.PRIMARY
                        ),
                        ft.Container(height=20),
                        ft.Text(
                            "Fetching and validating channels...",
                            color=AppColors.PRIMARY,
                            size=18,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "Please wait, massive playlists may take a moment.",
                            color=AppColors.GREY_DIM,
                            size=12,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
            return

        def _retry(e):
            if load_channels:
                page_obj.run_task(load_channels, True)

        target.controls.append(
            ft.Column(
                [
                    ft.Container(height=80),
                    ft.Icon(
                        ft.Icons.WIFI_OFF_ROUNDED, size=64, color=AppColors.WARNING
                    ),
                    ft.Container(height=16),
                    ft.Text(
                        "No channels available",
                        color=AppColors.PRIMARY,
                        size=18,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "Could not load network playlists. Check internet or retry.",
                        color=AppColors.GREY_DIM,
                        size=12,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=20),
                    ft.FilledButton(
                        "Retry Loading Channels",
                        on_click=_retry,
                        style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        return

    query = view_state.get("search_query", "").strip().lower()
    if query:
        groups = _search_channels(state.channels, query, tab_index)
    else:
        groups = _build_groups(state.channels, tab_index)

    if not groups and tab_index == 2:
        target.controls.append(
            ft.Column(
                [
                    ft.Container(height=40),
                    ft.Icon(
                        ft.Icons.ADD_TO_QUEUE_ROUNDED, size=48, color=AppColors.PRIMARY
                    ),
                    ft.Container(height=12),
                    ft.Text(
                        "No custom content added yet",
                        color=AppColors.PRIMARY,
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                    ft.Text(
                        "Tap the '+' button above to add custom playlists or stream URLs.",
                        color=AppColors.GREY_DIM,
                        size=12,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        return

    if not groups:
        target.controls.append(
            ft.Column(
                [
                    ft.Container(height=40),
                    ft.Icon(
                        ft.Icons.SEARCH_OFF_ROUNDED, size=48, color=AppColors.GREY_DIM
                    ),
                    ft.Container(height=12),
                    ft.Text(
                        f"No channels matching '{query}'",
                        color=AppColors.GREY_DIM,
                        size=14,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        return

    sorted_group_names = sorted(
        groups.keys(),
        key=lambda g: (
            0
            if g == state.user_country
            else 1
            if g == "Global"
            else 2
            if g.startswith("Custom")
            else 3,
            g,
        ),
    )

    is_searching = bool(query)

    for group_name in sorted_group_names:
        chans = groups[group_name]
        is_user_country = group_name == state.user_country
        should_expand = is_user_country or is_searching

        tile_controls = []
        if should_expand:
            end = min(PAGE_SIZE, len(chans))
            tile_controls.append(
                ft.Container(
                    content=ft.Text(
                        LBL_SHOWING_RANGE.format(start=1, end=end, total=len(chans)),
                        size=11,
                        color=AppColors.GREY_DIM,
                        italic=True,
                        text_align=ft.TextAlign.CENTER,
                        width=float("inf"),
                    ),
                    padding=ft.Padding(0, 5, 0, 5),
                )
            )
            ad_indices = {
                idx
                for idx in range(end)
                if (idx + 1) % 12 == 0 and (idx + 1) < len(chans)
            }
            grid = build_channel_grid(
                chans[:end],
                0,
                PAGE_SIZE,
                on_play=on_play,
                page_obj=page_obj,
                ad_service=ad_service,
                ad_indices=ad_indices,
            )
            tile_controls.append(grid)

            if len(chans) > PAGE_SIZE:
                remaining = len(chans) - PAGE_SIZE
                next_btn = build_nav_btn(
                    LBL_SHOW_NEXT.format(
                        count=min(PAGE_SIZE, remaining), remaining=remaining
                    ),
                    ft.Icons.EXPAND_MORE,
                    lambda e, g_chans=chans: show_page(
                        e.control.parent,
                        g_chans,
                        PAGE_SIZE,
                        page_obj,
                        on_play,
                        ad_service,
                        liveliness,
                    ),
                )
                tile_controls.append(next_btn)

        subtitle_text = f"{len(chans)} channels"
        if is_user_country:
            subtitle_text += " \u2022 Preferred Region"

        exp_tile = ft.ExpansionTile(
            title=ft.Text(
                group_name,
                weight=ft.FontWeight.BOLD,
                color=AppColors.PRIMARY if is_user_country else None,
            ),
            subtitle=ft.Text(
                subtitle_text,
                size=11,
                color=AppColors.PRIMARY if is_user_country else AppColors.GREY_DIM,
            ),
            expanded=should_expand,
            on_change=lambda e, g_chans=chans: _handle_expansion(
                e, g_chans, active_tiles, page_obj, on_play, ad_service, liveliness
            ),
            controls=tile_controls,
            collapsed_bgcolor=ft.Colors.TRANSPARENT,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
        )

        tile_wrapper = ft.Container(
            content=exp_tile,
            border_radius=12,
            ink=True,
            on_click=lambda e, t=exp_tile: (
                setattr(t, "expanded", not t.expanded) or t.update()
            ),
        )
        tile_wrapper.tab_index = 0

        active_tiles.append(exp_tile)
        target.controls.append(tile_wrapper)
