"""Folder renderers and page pagination for local video tab."""

import flet as ft

from core.constants import (
    LBL_GRANT_PERMISSION,
    LBL_NO_LOCAL_VIDEOS,
    LBL_PERMISSION_NEEDED,
    LBL_SCANNING_DEVICE,
    LBL_SCANNING_DEVICE_SUB,
    LBL_SHOWING_RANGE,
    PAGE_SIZE,
)
from core.theme import AppColors
from views.tabs.local.cards import _build_video_card
from views.tabs.local.expansion import _render_folder_tiles as _render_folder_tiles_impl


def _show_local_page(tile, folder, offset, page_obj, on_play):
    total = len(folder.videos)
    end = min(offset + PAGE_SIZE, total)

    has_remove_btn = (
        len(tile.controls) > 0
        and isinstance(tile.controls[0], ft.TextButton)
        and "Remove"
        in getattr(
            tile.controls[0].content,
            "value",
            getattr(tile.controls[0], "text", ""),
        )
    )
    preserved_btn = tile.controls[0] if has_remove_btn else None

    tile.controls.clear()
    if preserved_btn:
        tile.controls.append(preserved_btn)

    if offset > 0:
        prev_offset = max(0, offset - PAGE_SIZE)
        prev_btn = ft.TextButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.EXPAND_LESS, color=AppColors.PRIMARY),
                    ft.Text(
                        f"Show previous {offset - prev_offset}",
                        color=AppColors.PRIMARY,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.FOCUSED: ft.Colors.with_opacity(
                        0.12,
                        AppColors.PRIMARY,
                    ),
                },
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=10),
                side={
                    ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY),
                    ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY),
                },
            ),
            on_click=lambda e, off=prev_offset: _show_local_page(
                tile,
                folder,
                off,
                page_obj,
                on_play,
            ),
        )
        tile.controls.append(prev_btn)

    tile.controls.append(
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
        ),
    )

    grid = ft.ResponsiveRow(spacing=12, run_spacing=12)
    for i, v in enumerate(folder.videos[offset:end]):
        card = _build_video_card(v, offset + i, on_play, page_obj)
        wrapper = ft.Container(
            content=card,
            col={"xs": 4, "sm": 3, "md": 2, "lg": 2},
            padding=4,
        )
        grid.controls.append(wrapper)
    tile.controls.append(grid)

    hint = ft.Container(
        content=ft.Text(
            "Tap a file to play · Use D-pad to navigate",
            size=10,
            color=AppColors.GREY_DIM,
            italic=True,
            text_align=ft.TextAlign.CENTER,
        ),
        padding=ft.Padding(8, 4, 8, 4),
        border_radius=8,
        ink=True,
        on_click=lambda e: None,
    )
    hint.tab_index = 998
    tile.controls.append(hint)

    if end < total:
        remaining = total - end
        next_btn = ft.TextButton(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.EXPAND_MORE, color=AppColors.PRIMARY),
                    ft.Text(
                        f"Show next {min(PAGE_SIZE, remaining)} of {remaining} remaining",
                        color=AppColors.PRIMARY,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
            ),
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.FOCUSED: ft.Colors.with_opacity(
                        0.12,
                        AppColors.PRIMARY,
                    ),
                },
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=10),
                side={
                    ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY),
                    ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY),
                },
            ),
            on_click=lambda e, off=end: _show_local_page(
                tile,
                folder,
                off,
                page_obj,
                on_play,
            ),
        )
        tile.controls.append(next_btn)

    tile.update()


def _render_scanning(target):
    target.controls.append(
        ft.Column(
            [
                ft.Container(height=80),
                ft.ProgressRing(
                    width=60,
                    height=60,
                    stroke_width=6,
                    color=AppColors.PRIMARY,
                ),
                ft.Container(height=20),
                ft.Text(
                    LBL_SCANNING_DEVICE,
                    color=AppColors.GREY_DIM,
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(LBL_SCANNING_DEVICE_SUB, color=AppColors.GREY_DIM, size=12),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _render_permission_needed(target, on_grant):
    target.controls.append(
        ft.Column(
            [
                ft.Container(height=80),
                ft.Icon(ft.Icons.FOLDER_OPEN, size=64, color=AppColors.GREY_DIM),
                ft.Container(height=16),
                ft.Text(
                    LBL_PERMISSION_NEEDED,
                    color=AppColors.GREY_DIM,
                    size=16,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(height=20),
                ft.FilledButton(
                    content=LBL_GRANT_PERMISSION,
                    on_click=on_grant,
                    style=ft.ButtonStyle(
                        bgcolor=AppColors.PRIMARY,
                        padding=20,
                        shape=ft.RoundedRectangleBorder(radius=12),
                    ),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _render_no_videos(target):
    target.controls.append(
        ft.Column(
            [
                ft.Container(height=80),
                ft.Icon(ft.Icons.VIDEO_LIBRARY, size=64, color=AppColors.GREY_DIM),
                ft.Container(height=16),
                ft.Text(
                    LBL_NO_LOCAL_VIDEOS,
                    color=AppColors.GREY_DIM,
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "We scanned standard folders but couldn't find any videos.\nPlease tap the folder icon above to add a custom path.",
                    color=AppColors.GREY_DIM,
                    size=12,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _render_folder_tiles(
    target,
    folders,
    active_tiles,
    page_obj,
    on_play,
    custom_paths,
    on_remove_custom,
):
    _render_folder_tiles_impl(
        target,
        folders,
        active_tiles,
        page_obj,
        on_play,
        custom_paths,
        on_remove_custom,
        _show_local_page,
    )
