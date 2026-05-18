import asyncio
import contextlib
import os

import flet as ft

from components.ui.glass_container import GlassContainer
from core.constants import (
    LBL_GRANT_PERMISSION,
    LBL_LOCAL_VIDEOS,
    LBL_NO_LOCAL_VIDEOS,
    LBL_PERMISSION_NEEDED,
    LBL_REFRESH_LOCAL,
    LBL_SCANNING_DEVICE,
    LBL_SCANNING_DEVICE_SUB,
    LBL_SHOWING_RANGE,
)
from core.theme import AppColors
from services.local_scanner import (
    _format_size,
    get_default_scan_paths,
    scan_videos,
)

_scan_cache = {"folders": [], "timestamp": 0.0, "total_videos": 0}


def build_local_tab_content(page_obj: ft.Page, on_play: callable, ad_service):
    view_state = {
        "folders": [],
        "is_scanning": False,
        "permission_granted": False,
        "total_videos": 0,
    }

    local_content = ft.ListView(expand=True, spacing=15)
    _active_tiles = []
    PAGE_SIZE = 24

    def _build_video_card(video, idx=0):
        card_key = f"local_vid_{idx}"
        card_visual = GlassContainer(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=8, height=8, border_radius=4, bgcolor=AppColors.SUCCESS
                            )
                        ],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                    ft.Icon(ft.Icons.VIDEO_FILE, size=36, color=AppColors.PRIMARY),
                    ft.Text(
                        video.name,
                        size=11,
                        weight=ft.FontWeight.W_400,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(
                        _format_size(video.size),
                        size=9,
                        color=AppColors.GREY_DIM,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=2,
            ),
            padding=10,
            border_radius=25,
            focusable=True,
            key=card_key,
        )

        interactive_card = ft.Container(
            content=card_visual,
            border_radius=25,
            ink=True,
            height=130,
            on_click=lambda e, path=video.path: page_obj.run_task(
                on_play, path
            ),
        )

        return interactive_card

    def _build_page_grid(folder, offset=0, limit=24):
        page_videos = folder.videos[offset : offset + limit]
        grid = ft.ResponsiveRow(spacing=12, run_spacing=12)

        for i, v in enumerate(page_videos):
            global_idx = offset + i
            card = _build_video_card(v, idx=global_idx)
            card_wrapper = ft.Container(
                content=card,
                col={"xs": 4, "sm": 3, "md": 2, "lg": 2},
            )
            grid.controls.append(card_wrapper)

        return grid

    def _show_page(tile, folder, offset):
        total = len(folder.videos)
        end = min(offset + PAGE_SIZE, total)

        tile.controls.clear()

        if offset > 0:
            prev_offset = max(0, offset - PAGE_SIZE)
            prev_label = f"Show previous {offset - prev_offset} ▶"
            btn = ft.TextButton(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.EXPAND_LESS, color=AppColors.PRIMARY),
                        ft.Text(
                            prev_label,
                            color=AppColors.PRIMARY,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                style=ft.ButtonStyle(
                    bgcolor={
                        ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.12, AppColors.PRIMARY),
                    },
                    padding=15,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    side={
                        ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY),
                        ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY),
                    },
                ),
                on_click=lambda e, t=tile, f=folder, o=prev_offset: _show_page(
                    t, f, o
                ),
            )
            tile.controls.append(btn)

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
            )
        )

        grid = _build_page_grid(folder, offset, PAGE_SIZE)
        tile.controls.append(grid)

        if end < total:
            remaining = total - end
            next_label = f"Show next {min(PAGE_SIZE, remaining)} of {remaining} remaining ▶"
            btn = ft.TextButton(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.EXPAND_MORE, color=AppColors.PRIMARY),
                        ft.Text(
                            next_label,
                            color=AppColors.PRIMARY,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                style=ft.ButtonStyle(
                    bgcolor={
                        ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.12, AppColors.PRIMARY),
                    },
                    padding=15,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    side={
                        ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY),
                        ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY),
                    },
                ),
                on_click=lambda e, t=tile, f=folder, o=end: _show_page(t, f, o),
            )
            tile.controls.append(btn)

        tile.update()

    def _style_nav(control, focused):
        if focused:
            control.bgcolor = ft.Colors.with_opacity(0.1, AppColors.PRIMARY)
            control.border = ft.Border.all(2, AppColors.PRIMARY)
        else:
            control.bgcolor = None
            control.border = ft.Border.all(1.5, AppColors.PRIMARY)
        with contextlib.suppress(Exception):
            control.update()

    def _collapse_other_tiles(current_tile):
        for t in _active_tiles:
            if t is not current_tile and t.expanded:
                t.expanded = False
                t.visible = False
                with contextlib.suppress(Exception):
                    t.update()

    def handle_expansion(e, folder):
        if str(e.data).lower() == "true":
            _collapse_other_tiles(e.control)
            if not e.control.controls:
                _show_page(e.control, folder, 0)
            with contextlib.suppress(Exception):
                e.control.update()
        else:
            with contextlib.suppress(Exception):
                e.control.update()

    def _on_tile_focus(control, focused):
        if focused:
            control.collapsed_bgcolor = ft.Colors.with_opacity(
                0.12, AppColors.PRIMARY
            )
            control.bgcolor = ft.Colors.with_opacity(0.12, AppColors.PRIMARY)
            control.border = ft.Border.all(2, AppColors.PRIMARY)
            control.border_radius = 12
        else:
            control.collapsed_bgcolor = ft.Colors.TRANSPARENT
            control.bgcolor = ft.Colors.with_opacity(
                0.03, ft.Colors.ON_SURFACE
            )
            control.border = ft.Border.all(0, ft.Colors.TRANSPARENT)
            control.border_radius = 0
        with contextlib.suppress(Exception):
            control.update()

    def render_content():
        local_content.controls.clear()
        _active_tiles.clear()

        if view_state["is_scanning"]:
            local_content.controls.append(
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
                        ft.Text(
                            LBL_SCANNING_DEVICE_SUB,
                            color=AppColors.GREY_DIM,
                            size=12,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        elif not view_state["permission_granted"]:
            local_content.controls.append(
                ft.Column(
                    [
                        ft.Container(height=80),
                        ft.Icon(
                            ft.Icons.FOLDER_OPEN,
                            size=64,
                            color=AppColors.GREY_DIM,
                        ),
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
                            on_click=lambda _: page_obj.run_task(
                                request_and_scan
                            ),
                            style=ft.ButtonStyle(
                                bgcolor=AppColors.PRIMARY,
                                padding=20,
                                shape=ft.RoundedRectangleBorder(radius=12),
                            ),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        elif not view_state["folders"]:
            local_content.controls.append(
                ft.Column(
                    [
                        ft.Container(height=80),
                        ft.Icon(
                            ft.Icons.VIDEO_LIBRARY,
                            size=64,
                            color=AppColors.GREY_DIM,
                        ),
                        ft.Container(height=16),
                        ft.Text(
                            LBL_NO_LOCAL_VIDEOS,
                            color=AppColors.GREY_DIM,
                            size=16,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        else:
            for folder in view_state["folders"]:
                should_expand = len(view_state["folders"]) == 1

                tile_controls = []
                if should_expand:
                    grid = _build_page_grid(folder, 0, PAGE_SIZE)
                    total = len(folder.videos)
                    end = min(PAGE_SIZE, total)

                    tile_controls.append(
                        ft.Container(
                            content=ft.Text(
                                LBL_SHOWING_RANGE.format(
                                    start=1, end=end, total=total
                                ),
                                size=11,
                                color=AppColors.GREY_DIM,
                                italic=True,
                                text_align=ft.TextAlign.CENTER,
                                width=float("inf"),
                            ),
                            padding=ft.Padding(0, 5, 0, 5),
                        )
                    )
                    tile_controls.append(grid)

                    if total > PAGE_SIZE:
                        btn = ft.TextButton(
                            content=ft.Row(
                                [
                                    ft.Icon(
                                        ft.Icons.EXPAND_MORE,
                                        color=AppColors.PRIMARY,
                                    ),
                                    ft.Text(
                                        f"Show next {min(PAGE_SIZE, total - end)} of {total - end} remaining ▶",
                                        color=AppColors.PRIMARY,
                                        weight=ft.FontWeight.W_500,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=8,
                            ),
                            style=ft.ButtonStyle(
                                bgcolor={
                                    ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.12, AppColors.PRIMARY),
                                },
                                padding=15,
                                shape=ft.RoundedRectangleBorder(radius=10),
                                side={
                                    ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY),
                                    ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY),
                                },
                            ),
                        )
                        btn._needs_tile_ref = True
                        tile_controls.append(btn)

                exp_tile = ft.ExpansionTile(
                    title=ft.Text(
                        f"{folder.name} ({folder.count})",
                        weight=ft.FontWeight.BOLD,
                    ),
                    subtitle=ft.Text(
                        folder.path,
                        size=10,
                        color=AppColors.GREY_DIM,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    expanded=should_expand,
                    on_change=lambda e, f=folder: handle_expansion(e, f),
                    controls=tile_controls,
                    collapsed_bgcolor=ft.Colors.TRANSPARENT,
                    bgcolor=ft.Colors.with_opacity(
                        0.03, ft.Colors.ON_SURFACE
                    ),
                )

                tile_wrapper = ft.Container(
                    content=exp_tile,
                    border_radius=12,
                    ink=True,
                    on_click=lambda e, t=exp_tile: setattr(t, 'expanded', not t.expanded) or t.update(),
                )
                tile_wrapper.tab_index = 0
                tile_wrapper.on_focus = lambda e: _on_tile_focus(exp_tile, True)
                tile_wrapper.on_blur = lambda e: _on_tile_focus(exp_tile, False)

                if should_expand and total > PAGE_SIZE:
                    next_offset = min(PAGE_SIZE, total)
                    for ctrl in tile_controls:
                        if hasattr(ctrl, "_needs_tile_ref"):
                            ctrl.on_click = lambda e, t=exp_tile, f=folder, o=next_offset: _show_page(t, f, o)

                _active_tiles.append(exp_tile)
                local_content.controls.append(tile_wrapper)

        page_obj.update()

    async def request_and_scan(e=None):
        import time

        now = time.time()
        if _scan_cache["folders"] and (now - _scan_cache["timestamp"]) < 60:
            view_state["folders"] = _scan_cache["folders"]
            view_state["total_videos"] = _scan_cache["total"]
            view_state["permission_granted"] = True
            render_content()
            return

        view_state["is_scanning"] = True
        view_state["permission_granted"] = False
        render_content()

        try:
            import flet_permission_handler as fph

            ph = fph.PermissionHandler()

            status = await ph.get_status_async(fph.Permission.VIDEOS)
            if status != fph.PermissionStatus.GRANTED:
                status = await ph.request_async(fph.Permission.VIDEOS)

            if status == fph.PermissionStatus.GRANTED:
                view_state["permission_granted"] = True
            else:
                try:
                    status = await ph.get_status_async(fph.Permission.STORAGE)
                    if status != fph.PermissionStatus.GRANTED:
                        status = await ph.request_async(fph.Permission.STORAGE)
                    view_state["permission_granted"] = (
                        status == fph.PermissionStatus.GRANTED
                    )
                except Exception:
                    view_state["permission_granted"] = os.name != "nt"
        except Exception:
            if os.name == "nt":
                view_state["permission_granted"] = True
            else:
                view_state["permission_granted"] = False

        if view_state["permission_granted"]:
            await scan_local()
        else:
            view_state["is_scanning"] = False
            render_content()

    async def scan_local():
        import time

        view_state["is_scanning"] = True
        render_content()

        try:
            await asyncio.sleep(0.1)
            paths = get_default_scan_paths()
            folders = await asyncio.to_thread(scan_videos, paths)
            view_state["folders"] = folders
            view_state["total_videos"] = sum(f.count for f in folders)
            _scan_cache["folders"] = folders
            _scan_cache["total_videos"] = view_state["total_videos"]
            _scan_cache["timestamp"] = time.time()
        except Exception:
            view_state["folders"] = []
        finally:
            view_state["is_scanning"] = False
            render_content()

    def handle_refresh(e):
        refresh_btn.disabled = True
        page_obj.update()
        page_obj.run_task(scan_local)

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        on_click=handle_refresh,
        tooltip=LBL_REFRESH_LOCAL,
    )

    header = ft.Row(
        [
            ft.Text(LBL_LOCAL_VIDEOS, size=20, weight=ft.FontWeight.BOLD),
            refresh_btn,
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    main_col = ft.Column(
        [header, local_content],
        spacing=15,
        expand=True,
    )

    page_obj.run_task(request_and_scan)

    return main_col
