"""Expansion tile handlers for local video folders."""

import contextlib

import flet as ft

from core.constants import PAGE_SIZE
from core.theme import AppColors
from views.tabs.local.cards import _build_video_card


def _handle_local_expansion(
    e, folder, active_tiles, page_obj, on_play, show_local_page_fn
):
    if str(e.data).lower() == "true":
        for t in active_tiles:
            if t is not e.control and t.expanded:
                t.expanded = False
                with contextlib.suppress(Exception):
                    t.update()

        has_content = any(isinstance(c, ft.ResponsiveRow) for c in e.control.controls)
        if not has_content:
            show_local_page_fn(e.control, folder, 0, page_obj, on_play)

        with contextlib.suppress(Exception):
            e.control.update()


def _render_folder_tiles(
    target,
    folders,
    active_tiles,
    page_obj,
    on_play,
    custom_paths,
    on_remove_custom,
    show_local_page_fn,
):
    for folder in folders:
        should_expand = len(folders) == 1
        tile_controls = []

        if folder.path in custom_paths:
            remove_btn = ft.TextButton(
                "Remove Custom Folder",
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.ERROR,
                style=ft.ButtonStyle(color=ft.Colors.ERROR),
                on_click=lambda e, p=folder.path: page_obj.run_task(
                    on_remove_custom,
                    p,
                ),
            )
            tile_controls.append(remove_btn)

        if should_expand:
            total = len(folder.videos)
            end = min(PAGE_SIZE, total)
            grid = ft.ResponsiveRow(spacing=12, run_spacing=12)
            for i, v in enumerate(folder.videos[:end]):
                card = _build_video_card(v, i, on_play, page_obj)
                grid.controls.append(
                    ft.Container(
                        content=card, col={"xs": 4, "sm": 3, "md": 2, "lg": 2}
                    ),
                )

            tile_controls.append(
                ft.Container(
                    content=ft.Text(
                        f"Showing 1–{end} of {total}",
                        size=11,
                        color=AppColors.GREY_DIM,
                        italic=True,
                        text_align=ft.TextAlign.CENTER,
                        width=float("inf"),
                    ),
                    padding=ft.Padding(0, 5, 0, 5),
                ),
            )
            tile_controls.append(grid)

        exp_tile = ft.ExpansionTile(
            title=ft.Text(f"{folder.name} ({folder.count})", weight=ft.FontWeight.BOLD),
            subtitle=ft.Text(
                folder.path,
                size=10,
                color=AppColors.GREY_DIM,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
            expanded=should_expand,
            on_change=lambda e, f=folder: _handle_local_expansion(
                e,
                f,
                active_tiles,
                page_obj,
                on_play,
                show_local_page_fn,
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

        if should_expand and len(folder.videos) > PAGE_SIZE:
            next_offset = PAGE_SIZE
            total = len(folder.videos)
            remaining = total - next_offset
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
                on_click=lambda e, t=exp_tile, f=folder: show_local_page_fn(
                    t,
                    f,
                    PAGE_SIZE,
                    page_obj,
                    on_play,
                ),
            )
            tile_controls.append(next_btn)

        active_tiles.append(exp_tile)
        target.controls.append(tile_wrapper)
