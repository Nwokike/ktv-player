"""Pagination controls for channel grids."""


import flet as ft

from core.constants import (
    LBL_SHOW_NEXT,
    LBL_SHOW_PREVIOUS,
    LBL_SHOWING_RANGE,
    PAGE_SIZE,
)
from core.theme import AppColors


def build_nav_btn(icon, label, **kwargs):
    """Build a styled pagination button using Container (D-pad focusable)."""



    btn = ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=AppColors.PRIMARY),
                ft.Text(label, color=AppColors.PRIMARY, weight=ft.FontWeight.W_500),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=8,
        ),
        padding=15,
        border_radius=10,
        border=ft.Border.all(1.5, AppColors.PRIMARY),
        ink=True,
        animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
    )
    btn.tab_index = 900
    return btn


def show_page(tile, channels, offset, page_obj, on_play, ad_service, liveliness):
    """Display a page of channels inside an expansion tile."""
    from components.ui.channel_grid import build_channel_grid

    total = len(channels)
    end = min(offset + PAGE_SIZE, total)

    # Build new controls list
    new_controls = []

    # Previous page button
    if offset > 0:
        prev_offset = max(0, offset - PAGE_SIZE)
        prev_label = LBL_SHOW_PREVIOUS.format(
            count=offset - prev_offset, start=prev_offset + 1, end=offset
        )
        prev_btn = build_nav_btn(ft.Icons.EXPAND_LESS, prev_label)
        prev_btn.on_click = lambda e, off=prev_offset: show_page(
            tile, channels, off, page_obj, on_play, ad_service, liveliness
        )
        new_controls.append(prev_btn)

    # Range indicator
    new_controls.append(
        ft.Container(
            content=ft.Text(
                LBL_SHOWING_RANGE.format(start=offset + 1, end=end, total=total),
                size=11,
                color=AppColors.GREY_DIM,
                italic=True,
                text_align=ft.TextAlign.CENTER,
                width=float("inf"),
            ),
            padding=ft.Padding(0, 5, 0, 5),
        )
    )

    # Channel grid
    page_end = min(offset + PAGE_SIZE, total)
    ad_indices = {
        idx
        for idx in range(offset, page_end)
        if (idx + 1) % 12 == 0 and (idx + 1) < total
    }
    grid = build_channel_grid(
        channels,
        offset,
        PAGE_SIZE,
        on_play=on_play,
        page_obj=page_obj,
        ad_service=ad_service,
        ad_indices=ad_indices,
    )
    new_controls.append(grid)

    # D-pad focus anchor

    hint_btn = ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    width=8, height=8, border_radius=4, bgcolor=ft.Colors.GREEN
                ),
                ft.Text("Live", size=10, color=AppColors.GREY_DIM),
                ft.Container(width=8, height=8, border_radius=4, bgcolor=ft.Colors.RED),
                ft.Text(
                    "Offline — Play green channels",
                    size=10,
                    color=AppColors.GREY_DIM,
                    italic=True,
                ),
            ],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        padding=ft.Padding(8, 4, 8, 4),
        border_radius=8,
        ink=True,
        on_click=lambda e: None,
    )
    hint_btn.tab_index = 998
    new_controls.append(hint_btn)

    # Next page button
    if end < total:
        remaining = total - end
        show_count = min(PAGE_SIZE, remaining)
        next_label = LBL_SHOW_NEXT.format(count=show_count, remaining=remaining)
        next_btn = build_nav_btn(ft.Icons.EXPAND_MORE, next_label)
        next_btn.on_click = lambda e, off=end: show_page(
            tile, channels, off, page_obj, on_play, ad_service, liveliness
        )
        new_controls.append(next_btn)

    # Single atomic swap
    tile.controls.clear()
    tile.controls.extend(new_controls)
    tile.update()

    # Fire liveliness checks after render
    cards_data = liveliness.collect_cards_data(grid)
    if cards_data:
        page_obj.run_task(liveliness.fire_batch, cards_data)
