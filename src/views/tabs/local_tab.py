"""Local video tab — scans device storage for video files."""
import asyncio
import contextlib
import logging
import os
import time

import flet as ft

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
from core.focus_manager import make_focusable_card
from core.theme import AppColors
from services.local_scanner import _format_size, get_default_scan_paths, scan_videos

logger = logging.getLogger(__name__)

_scan_cache = {"folders": [], "timestamp": 0.0}

# PermissionHandler + StoragePaths are Services — imported at runtime to avoid crash on desktop
_ph = None  # PermissionHandler instance (added to page.overlay once)
_sp = None  # StoragePaths instance


def _hint_focus_local(control, focused):
    control.bgcolor = ft.Colors.with_opacity(0.08, AppColors.PRIMARY) if focused else None
    with contextlib.suppress(Exception):
        control.update()


# --- Permission helpers ---

def _is_mobile() -> bool:
    """Detect if running on Android/iOS (not desktop/web)."""
    return os.name != "nt" and not os.environ.get("FLET_WEB")


async def _ensure_services(page_obj):
    """Register PermissionHandler and StoragePaths services once (mobile only)."""
    global _ph, _sp

    if not _is_mobile():
        return

    if _sp is None:
        try:
            _sp = ft.StoragePaths()
            page_obj.overlay.append(_sp)
        except Exception:
            logger.warning("StoragePaths not available")

    if _ph is None:
        try:
            from flet_permission_handler import PermissionHandler
            _ph = PermissionHandler()
            page_obj.overlay.append(_ph)
        except (ImportError, Exception):
            logger.warning("flet-permission-handler not available")

    page_obj.update()


async def _request_storage_permission() -> bool:
    """Request storage permission on Android. Returns True if granted."""
    if not _is_mobile() or _ph is None:
        return True  # Desktop — always granted

    try:
        from flet_permission_handler import Permission, PermissionStatus

        # Android 13+ uses Permission.VIDEOS, older uses Permission.STORAGE
        status = await _ph.request(Permission.VIDEOS)
        if status == PermissionStatus.GRANTED:
            return True

        # Fallback for older Android
        status = await _ph.request(Permission.STORAGE)
        if status == PermissionStatus.GRANTED:
            return True

        # If permanently denied, open app settings
        if status == PermissionStatus.PERMANENTLY_DENIED:
            await _ph.open_app_settings()

        return False
    except Exception:
        logger.exception("Permission request failed")
        return True  # Fail open on error — try scanning anyway


async def _get_scan_paths() -> list[str]:
    """Get scan paths using StoragePaths on Android, fallback to defaults."""
    paths = []

    if _is_mobile() and _sp is not None:
        try:
            ext_dir = await _sp.get_external_storage_directory()
            if ext_dir:
                paths.append(ext_dir)
        except Exception:
            pass

        try:
            ext_dirs = await _sp.get_external_storage_directories()
            if ext_dirs:
                paths.extend(ext_dirs)
        except Exception:
            pass

        try:
            dl_dir = await _sp.get_downloads_directory()
            if dl_dir:
                paths.append(dl_dir)
        except Exception:
            pass

    # Deduplicate and add defaults if nothing found
    paths = list(dict.fromkeys(paths))  # preserve order, remove dupes
    if not paths:
        paths = get_default_scan_paths()

    return paths


# --- UI Builders ---

def _build_video_card(video, idx, on_play, page_obj):
    card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [ft.Container(width=8, height=8, border_radius=4, bgcolor=AppColors.SUCCESS)],
                    alignment=ft.MainAxisAlignment.END,
                ),
                ft.Icon(ft.Icons.VIDEO_FILE, size=36, color=AppColors.PRIMARY),
                ft.Text(
                    video.name, size=11, weight=ft.FontWeight.W_400,
                    text_align=ft.TextAlign.CENTER, max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    _format_size(video.size), size=9, color=AppColors.GREY_DIM,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2,
        ),
        padding=10,
        border_radius=25,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        border=ft.Border.all(0.5, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        ink=True,
        height=130,
        key=f"local_vid_{idx}",
        on_click=lambda e, path=video.path: page_obj.run_task(on_play, path),
    )
    card.tab_index = idx + 10
    make_focusable_card(card)

    return card


def _show_local_page(tile, folder, offset, page_obj, on_play):
    total = len(folder.videos)
    end = min(offset + PAGE_SIZE, total)
    tile.controls.clear()

    if offset > 0:
        prev_offset = max(0, offset - PAGE_SIZE)
        prev_btn = ft.TextButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.EXPAND_LESS, color=AppColors.PRIMARY),
                 ft.Text(f"Show previous {offset - prev_offset}", color=AppColors.PRIMARY, weight=ft.FontWeight.W_500)],
                alignment=ft.MainAxisAlignment.CENTER, spacing=8,
            ),
            style=ft.ButtonStyle(
                bgcolor={ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.12, AppColors.PRIMARY)},
                padding=15, shape=ft.RoundedRectangleBorder(radius=10),
                side={ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY), ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY)},
            ),
            on_click=lambda e, off=prev_offset: _show_local_page(tile, folder, off, page_obj, on_play),
        )
        tile.controls.append(prev_btn)

    tile.controls.append(
        ft.Container(
            content=ft.Text(
                LBL_SHOWING_RANGE.format(start=offset + 1, end=end, total=total),
                size=11, color=AppColors.GREY_DIM, italic=True,
                text_align=ft.TextAlign.CENTER, width=float("inf"),
            ),
            padding=ft.Padding(0, 5, 0, 5),
        )
    )

    grid = ft.ResponsiveRow(spacing=12, run_spacing=12)
    for i, v in enumerate(folder.videos[offset:end]):
        card = _build_video_card(v, offset + i, on_play, page_obj)
        wrapper = ft.Container(content=card, col={"xs": 4, "sm": 3, "md": 2, "lg": 2}, padding=4)
        grid.controls.append(wrapper)
    tile.controls.append(grid)

    # D-pad focus anchor (sibling of grid, not inside it)
    hint = ft.Container(
        content=ft.Text("Tap a file to play · Use D-pad to navigate", size=10, color=AppColors.GREY_DIM, italic=True, text_align=ft.TextAlign.CENTER),
        padding=ft.Padding(8, 4, 8, 4),
        border_radius=8,
        ink=True,
        on_click=lambda e: None,
    )
    hint.tab_index = 998
    hint.on_focus = lambda e: _hint_focus_local(e.control, True)
    hint.on_blur = lambda e: _hint_focus_local(e.control, False)
    tile.controls.append(hint)

    if end < total:
        remaining = total - end
        next_btn = ft.TextButton(
            content=ft.Row(
                [ft.Icon(ft.Icons.EXPAND_MORE, color=AppColors.PRIMARY),
                 ft.Text(f"Show next {min(PAGE_SIZE, remaining)} of {remaining} remaining", color=AppColors.PRIMARY, weight=ft.FontWeight.W_500)],
                alignment=ft.MainAxisAlignment.CENTER, spacing=8,
            ),
            style=ft.ButtonStyle(
                bgcolor={ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.12, AppColors.PRIMARY)},
                padding=15, shape=ft.RoundedRectangleBorder(radius=10),
                side={ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY), ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY)},
            ),
            on_click=lambda e, off=end: _show_local_page(tile, folder, off, page_obj, on_play),
        )
        tile.controls.append(next_btn)

    tile.update()


def _on_tile_focus(control, focused):
    if focused:
        control.collapsed_bgcolor = ft.Colors.with_opacity(0.12, AppColors.PRIMARY)
        control.bgcolor = ft.Colors.with_opacity(0.12, AppColors.PRIMARY)
        control.border = ft.Border.all(2, AppColors.PRIMARY)
        control.border_radius = 12
    else:
        control.collapsed_bgcolor = ft.Colors.TRANSPARENT
        control.bgcolor = ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE)
        control.border = ft.Border.all(0, ft.Colors.TRANSPARENT)
        control.border_radius = 0
    with contextlib.suppress(Exception):
        control.update()


def _render_scanning(target):
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


def _render_permission_needed(target, on_grant):
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
                    on_click=on_grant,
                    style=ft.ButtonStyle(bgcolor=AppColors.PRIMARY, padding=20, shape=ft.RoundedRectangleBorder(radius=12)),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )


def _render_no_videos(target):
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


def _render_folder_tiles(target, folders, active_tiles, page_obj, on_play):
    for folder in folders:
        should_expand = len(folders) == 1

        tile_controls = []
        if should_expand:
            total = len(folder.videos)
            end = min(PAGE_SIZE, total)
            grid = ft.ResponsiveRow(spacing=12, run_spacing=12)
            for i, v in enumerate(folder.videos[:end]):
                card = _build_video_card(v, i, on_play, page_obj)
                grid.controls.append(ft.Container(content=card, col={"xs": 4, "sm": 3, "md": 2, "lg": 2}))

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

        exp_tile = ft.ExpansionTile(
            title=ft.Text(f"{folder.name} ({folder.count})", weight=ft.FontWeight.BOLD),
            subtitle=ft.Text(folder.path, size=10, color=AppColors.GREY_DIM, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
            expanded=should_expand,
            on_change=lambda e, f=folder: _handle_local_expansion(e, f, active_tiles, page_obj, on_play),
            controls=tile_controls,
            collapsed_bgcolor=ft.Colors.TRANSPARENT,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.ON_SURFACE),
        )

        tile_wrapper = ft.Container(
            content=exp_tile, border_radius=12, ink=True,
            on_click=lambda e, t=exp_tile: setattr(t, "expanded", not t.expanded) or t.update(),
        )
        tile_wrapper.tab_index = 0
        tile_wrapper.on_focus = lambda e, t=exp_tile: _on_tile_focus(t, True)
        tile_wrapper.on_blur = lambda e, t=exp_tile: _on_tile_focus(t, False)

        # Add "next" button if expanded with lots of videos
        if should_expand and len(folder.videos) > PAGE_SIZE:
            next_offset = PAGE_SIZE
            total = len(folder.videos)
            remaining = total - next_offset
            next_btn = ft.TextButton(
                content=ft.Row(
                    [ft.Icon(ft.Icons.EXPAND_MORE, color=AppColors.PRIMARY),
                     ft.Text(f"Show next {min(PAGE_SIZE, remaining)} of {remaining} remaining", color=AppColors.PRIMARY, weight=ft.FontWeight.W_500)],
                    alignment=ft.MainAxisAlignment.CENTER, spacing=8,
                ),
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.FOCUSED: ft.Colors.with_opacity(0.12, AppColors.PRIMARY)},
                    padding=15, shape=ft.RoundedRectangleBorder(radius=10),
                    side={ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY), ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY)},
                ),
                on_click=lambda e, t=exp_tile, f=folder: _show_local_page(t, f, PAGE_SIZE, page_obj, on_play),
            )
            tile_controls.append(next_btn)

        active_tiles.append(exp_tile)
        target.controls.append(tile_wrapper)


def _handle_local_expansion(e, folder, active_tiles, page_obj, on_play):
    if str(e.data).lower() == "true":
        for t in active_tiles:
            if t is not e.control and t.expanded:
                t.expanded = False
                with contextlib.suppress(Exception):
                    t.update()
        if not e.control.controls:
            _show_local_page(e.control, folder, 0, page_obj, on_play)
        with contextlib.suppress(Exception):
            e.control.update()


# --- Scanning ---

async def _scan_device():
    paths = await _get_scan_paths()
    return await asyncio.to_thread(scan_videos, paths)


# --- Main Entry Point ---

def build_local_tab_content(target, page_obj, on_play, ad_service, liveliness, view_state, active_tiles):
    """Build the local videos tab."""

    def render():
        target.controls.clear()
        target.controls.append(header)
        active_tiles.clear()

        is_scanning = view_state.get("local_is_scanning", False)
        permission_granted = view_state.get("local_permission_granted", False)
        folders = view_state.get("local_folders", [])

        if is_scanning:
            _render_scanning(target)
        elif not permission_granted:
            _render_permission_needed(target, lambda _: page_obj.run_task(request_and_scan))
        elif not folders:
            _render_no_videos(target)
        else:
            _render_folder_tiles(target, folders, active_tiles, page_obj, on_play)

        page_obj.update()

    async def request_and_scan():
        now = time.time()
        if _scan_cache["folders"] and (now - _scan_cache["timestamp"]) < LOCAL_SCAN_CACHE_TTL:
            view_state["local_folders"] = _scan_cache["folders"]
            view_state["local_permission_granted"] = True
            render()
            return

        # Register services
        await _ensure_services(page_obj)

        # Request permission on Android
        granted = await _request_storage_permission()
        view_state["local_permission_granted"] = granted

        if not granted:
            render()
            return

        view_state["local_is_scanning"] = True
        render()

        try:
            await asyncio.sleep(0.1)
            folders = await _scan_device()
            view_state["local_folders"] = folders
            _scan_cache["folders"] = folders
            _scan_cache["timestamp"] = time.time()
        except Exception:
            logger.exception("Local scan failed")
            view_state["local_folders"] = []

        view_state["local_is_scanning"] = False
        render()

    async def scan_local():
        view_state["local_is_scanning"] = True
        render()
        try:
            await asyncio.sleep(0.1)
            folders = await _scan_device()
            view_state["local_folders"] = folders
            _scan_cache["folders"] = folders
            _scan_cache["timestamp"] = time.time()
        except Exception:
            logger.exception("Local scan failed")
            view_state["local_folders"] = []
        finally:
            view_state["local_is_scanning"] = False
            render()

    def handle_refresh(e):
        refresh_btn.disabled = True
        page_obj.update()
        page_obj.run_task(scan_local)

    refresh_btn = ft.IconButton(icon=ft.Icons.REFRESH, on_click=handle_refresh, tooltip=LBL_REFRESH_LOCAL)
    header = ft.Row(
        [ft.Text(LBL_LOCAL_VIDEOS, size=20, weight=ft.FontWeight.BOLD), refresh_btn],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    target.controls.append(header)
    page_obj.run_task(request_and_scan)
