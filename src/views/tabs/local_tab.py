import asyncio
import contextlib
import logging
import os
import time

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
    LOCAL_SCAN_CACHE_TTL,
    PAGE_SIZE,
)
from core.theme import AppColors
from services.local_scanner import (
    _format_size,
    get_default_scan_paths,
    scan_videos,
)
from views.tabs import (
    build_nav_btn,
    collapse_other_tiles,
    on_tile_focus,
)

logger = logging.getLogger(__name__)

_scan_cache = {"folders": [], "timestamp": 0.0, "total_videos": 0}


def build_local_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, active_tiles):
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
            on_click=lambda e, path=video.path: page_obj.run_task(on_play, path),
        )

        return interactive_card

    def _build_page_grid(folder, offset=0, limit=24):
        page_videos = folder.videos[offset: offset + limit]
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

    def _show_local_page(tile, folder, offset):
        total = len(folder.videos)
        end = min(offset + PAGE_SIZE, total)

        tile.controls.clear()

        if offset > 0:
            prev_offset = max(0, offset - PAGE_SIZE)
            prev_label = f"Show previous {offset - prev_offset} \u25b6"
            tile.controls.append(
                build_nav_btn(
                    ft.Icons.EXPAND_LESS, prev_label, tile, folder.videos, prev_offset,
                    page_obj, on_play, ad_service, liveliness, set(), is_next=False,
                )
            )

        tile.controls.append(
            ft.Container(
                content=ft.Text(
                    LBL_SHOWING_RANGE.format(start=offset + 1, end=end, total=total),
                    size=11, color=AppColors.GREY_DIM, italic=True,
                    text_align=ft.TextAlign.CENTER, width=float("inf"),
                ),
                padding=ft.Padding(0, 5, 0, 5),
            ),
        )

        grid = _build_page_grid(folder, offset, PAGE_SIZE)
        tile.controls.append(grid)

        if end < total:
            remaining = total - end
            next_label = f"Show next {min(PAGE_SIZE, remaining)} of {remaining} remaining \u25b6"
            nav_btn = build_nav_btn(
                ft.Icons.EXPAND_MORE, next_label, tile, folder.videos, end,
                page_obj, on_play, ad_service, liveliness, set(), is_next=True,
            )
            nav_btn._needs_tile_ref = True
            tile.controls.append(nav_btn)

        tile.update()

    def handle_local_expansion(e, folder):
        if str(e.data).lower() == "true":
            collapse_other_tiles(e.control, active_tiles)
            if not e.control.controls:
                _show_local_page(e.control, folder, 0)
            with contextlib.suppress(Exception):
                e.control.update()
        else:
            with contextlib.suppress(Exception):
                e.control.update()

    def render_content():
        target.controls.clear()
        active_tiles.clear()

        folders = view_state.get("local_folders", [])
        is_scanning = view_state.get("local_is_scanning", False)
        permission_granted = view_state.get("local_permission_granted", False)

        if is_scanning:
            target.controls.append(
                ft.Column(
                    [
                        ft.Container(height=80),
                        ft.ProgressRing(width=60, height=60, stroke_width=6, color=AppColors.PRIMARY),
                        ft.Container(height=20),
                        ft.Text(LBL_SCANNING_DEVICE, color=AppColors.GREY_DIM, size=18, weight=ft.FontWeight.BOLD),
                        ft.Text(LBL_SCANNING_DEVICE_SUB, color=AppColors.GREY_DIM, size=12),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        elif not permission_granted:
            target.controls.append(
                ft.Column(
                    [
                        ft.Container(height=80),
                        ft.Icon(ft.Icons.FOLDER_OPEN, size=64, color=AppColors.GREY_DIM),
                        ft.Container(height=16),
                        ft.Text(LBL_PERMISSION_NEEDED, color=AppColors.GREY_DIM, size=16, text_align=ft.TextAlign.CENTER),
                        ft.Container(height=20),
                        ft.FilledButton(
                            content=LBL_GRANT_PERMISSION,
                            on_click=lambda _: page_obj.run_task(request_and_scan),
                            style=ft.ButtonStyle(
                                bgcolor=AppColors.PRIMARY, padding=20, shape=ft.RoundedRectangleBorder(radius=12),
                            ),
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        elif not folders:
            target.controls.append(
                ft.Column(
                    [
                        ft.Container(height=80),
                        ft.Icon(ft.Icons.VIDEO_LIBRARY, size=64, color=AppColors.GREY_DIM),
                        ft.Container(height=16),
                        ft.Text(LBL_NO_LOCAL_VIDEOS, color=AppColors.GREY_DIM, size=16, text_align=ft.TextAlign.CENTER),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        else:
            for folder in folders:
                should_expand = len(folders) == 1

                tile_controls = []
                if should_expand:
                    grid = _build_page_grid(folder, 0, PAGE_SIZE)
                    total = len(folder.videos)
                    end = min(PAGE_SIZE, total)

                    tile_controls.append(
                        ft.Container(
                            content=ft.Text(
                                LBL_SHOWING_RANGE.format(start=1, end=end, total=total),
                                size=11, color=AppColors.GREY_DIM, italic=True,
                                text_align=ft.TextAlign.CENTER, width=float("inf"),
                            ),
                            padding=ft.Padding(0, 5, 0, 5),
                        )
                    )
                    tile_controls.append(grid)

                    if total > PAGE_SIZE:
                        btn = ft.TextButton(
                            content=ft.Row(
                                [
                                    ft.Icon(ft.Icons.EXPAND_MORE, color=AppColors.PRIMARY),
                                    ft.Text(
                                        f"Show next {min(PAGE_SIZE, total - end)} of {total - end} remaining \u25b6",
                                        color=AppColors.PRIMARY, weight=ft.FontWeight.W_500,
                                    ),
                                ],
                                alignment=ft.MainAxisAlignment.CENTER, spacing=8,
                            ),
                            style=ft.ButtonStyle(
                                bgcolor={ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.12, AppColors.PRIMARY)},
                                padding=15, shape=ft.RoundedRectangleBorder(radius=10),
                                side={
                                    ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY),
                                    ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY),
                                },
                            ),
                        )
                        btn._needs_tile_ref = True
                        tile_controls.append(btn)

                exp_tile = ft.ExpansionTile(
                    title=ft.Text(f"{folder.name} ({folder.count})", weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(
                        folder.path, size=10, color=AppColors.GREY_DIM,
                        max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    expanded=should_expand,
                    on_change=lambda e, f=folder: handle_local_expansion(e, f),
                    controls=tile_controls,
                    collapsed_bgcolor=ft.Colors.TRANSPARENT,
                    bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
                )

                tile_wrapper = ft.Container(
                    content=exp_tile,
                    border_radius=12,
                    ink=True,
                    on_click=lambda e, t=exp_tile: setattr(t, 'expanded', not t.expanded) or t.update(),
                )
                tile_wrapper.tab_index = 0
                tile_wrapper.on_focus = lambda e, t=exp_tile: on_tile_focus(t, True)
                tile_wrapper.on_blur = lambda e, t=exp_tile: on_tile_focus(t, False)

                if should_expand and total > PAGE_SIZE:
                    next_offset = min(PAGE_SIZE, total)
                    for ctrl in tile_controls:
                        if hasattr(ctrl, "_needs_tile_ref"):
                            ctrl.on_click = lambda e, t=exp_tile, f=folder, o=next_offset: _show_local_page(t, f, o)

                active_tiles.append(exp_tile)
                target.controls.append(tile_wrapper)

        page_obj.update()

    async def request_and_scan(e=None):
        now = time.time()
        if _scan_cache["folders"] and (now - _scan_cache["timestamp"]) < LOCAL_SCAN_CACHE_TTL:
            view_state["local_folders"] = _scan_cache["folders"]
            view_state["local_total_videos"] = _scan_cache["total_videos"]
            view_state["local_permission_granted"] = True
            render_content()
            return

        view_state["local_is_scanning"] = True
        view_state["local_permission_granted"] = False
        render_content()

        permission_granted = False

        if os.name != "nt":
            try:
                import flet_permission_handler as fph

                ph = fph.PermissionHandler()

                permission_types = [
                    (fph.Permission.READ_MEDIA_VIDEO, "READ_MEDIA_VIDEO"),
                    (fph.Permission.VIDEOS, "VIDEOS"),
                    (fph.Permission.READ_EXTERNAL_STORAGE, "READ_EXTERNAL_STORAGE"),
                ]

                for perm, perm_name in permission_types:
                    try:
                        status = await ph.get_status(perm)
                        logger.debug("Permission %s status: %s", perm_name, status)
                        if status == fph.PermissionStatus.GRANTED:
                            permission_granted = True
                            logger.info("Permission %s already granted", perm_name)
                            break
                    except Exception as exc:
                        logger.debug("get_status(%s) failed: %s", perm_name, exc)

                if not permission_granted:
                    for perm, perm_name in permission_types:
                        try:
                            logger.info("Requesting permission: %s", perm_name)
                            status = await ph.request(perm)
                            logger.debug("Permission %s request result: %s", perm_name, status)
                            if status == fph.PermissionStatus.GRANTED:
                                permission_granted = True
                                logger.info("Permission %s granted after request", perm_name)
                                break
                        except Exception as exc:
                            logger.debug("request(%s) failed: %s", perm_name, exc)
            except ImportError:
                logger.warning("flet_permission_handler not available, will attempt scan without permission")
            except Exception:
                logger.exception("Permission handling failed")

            if not permission_granted:
                logger.info("Permissions not granted, attempting scan anyway (scoped storage may allow it)")
                permission_granted = True
        else:
            permission_granted = True

        view_state["local_permission_granted"] = permission_granted

        if permission_granted:
            await scan_local()
        else:
            view_state["local_is_scanning"] = False
            render_content()

    async def scan_local():
        view_state["local_is_scanning"] = True
        render_content()

        try:
            await asyncio.sleep(0.1)
            paths = get_default_scan_paths()
            folders = await asyncio.to_thread(scan_videos, paths)
            view_state["local_folders"] = folders
            view_state["local_total_videos"] = sum(f.count for f in folders)
            _scan_cache["folders"] = folders
            _scan_cache["total_videos"] = view_state["local_total_videos"]
            _scan_cache["timestamp"] = time.time()
        except Exception:
            logger.exception("Local scan failed")
            view_state["local_folders"] = []
        finally:
            view_state["local_is_scanning"] = False
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

    target.controls.append(header)

    page_obj.run_task(request_and_scan)
