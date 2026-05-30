"""Local video tab — scans device storage for video files."""

import asyncio
import contextlib
import logging
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
from core.theme import AppColors
from services.local_scanner import (
    _format_size,
    get_default_scan_paths,
    is_mobile,
    scan_videos,
)

logger = logging.getLogger(__name__)

_scan_cache = {"folders": [], "timestamp": 0.0}

# Services — imported at runtime to avoid crash on desktop
_ph = None  # PermissionHandler instance
_sp = None  # StoragePaths instance
_fp = None  # FilePicker instance





# --- Permission & Service Helpers ---


async def _ensure_services(page_obj):
    """Register Services once."""
    global _ph, _sp, _fp

    # Register FilePicker (Flet 1.0+ Service - Do NOT append to overlay)
    if _fp is None:
        try:
            _fp = ft.FilePicker()
        except Exception:
            logger.warning("FilePicker not available")

    if not is_mobile():
        page_obj.update()
        return

    # Register StoragePaths (Mobile Only)
    if _sp is None:
        try:
            _sp = ft.StoragePaths()
        except Exception:
            logger.warning("StoragePaths not available")

    # Register PermissionHandler (Mobile Only)
    if _ph is None:
        try:
            from flet_permission_handler import PermissionHandler

            _ph = PermissionHandler()
        except (ImportError, Exception):
            logger.warning("flet-permission-handler not available")

    page_obj.update()


async def _request_storage_permission() -> bool:
    """Request standard, Play Store-compliant storage permission on Android."""
    if not is_mobile() or _ph is None:
        return True  # Desktop — always granted

    try:
        from flet_permission_handler import Permission, PermissionStatus

        # Android 13+ strict Media permission
        status = await _ph.request(Permission.VIDEOS)
        if status == PermissionStatus.GRANTED:
            return True

        # Fallback for older Android (Android 10 and below)
        status = await _ph.request(Permission.STORAGE)
        if status == PermissionStatus.GRANTED:
            return True

        # If permanently denied, open app settings so user can manually allow
        if status == PermissionStatus.PERMANENTLY_DENIED:
            await _ph.open_app_settings()

        return False
    except Exception as e:
        logger.exception(f"Permission request failed: {e}")
        return True  # Fail open on error — try scanning anyway


async def _get_scan_paths(custom_paths: list[str] = None) -> list[str]:
    """Get scan paths using StoragePaths, targeting safe media folders, plus custom paths."""
    paths = list(custom_paths) if custom_paths else []

    if is_mobile() and _sp is not None:
        try:
            # Get the root, but do NOT scan it directly to avoid Scoped Storage PermissionErrors
            ext_dir = await _sp.get_external_storage_directory()
            if ext_dir:
                paths.extend(
                    [
                        f"{ext_dir}/Movies",
                        f"{ext_dir}/Download",
                        f"{ext_dir}/DCIM",
                        f"{ext_dir}/Pictures",
                        f"{ext_dir}/Video",
                    ]
                )
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
                    [
                        ft.Container(
                            width=8,
                            height=8,
                            border_radius=4,
                            bgcolor=AppColors.SUCCESS,
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
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        border=ft.Border.all(0.5, ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE)),
        ink=True,
        height=130,
        key=f"local_vid_{idx}",
        on_click=lambda e, path=video.path: page_obj.run_task(on_play, path),
    )
    card.tab_index = idx + 10

    return card


def _show_local_page(tile, folder, offset, page_obj, on_play):
    total = len(folder.videos)
    end = min(offset + PAGE_SIZE, total)

    # Preserve the "Remove Custom Folder" button if it exists (it's always index 0 if present)
    has_remove_btn = (
        len(tile.controls) > 0
        and isinstance(tile.controls[0], ft.TextButton)
        and "Remove"
        in getattr(
            tile.controls[0].content, "value", getattr(tile.controls[0], "text", "")
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
                        0.12, AppColors.PRIMARY
                    )
                },
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=10),
                side={
                    ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY),
                    ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY),
                },
            ),
            on_click=lambda e, off=prev_offset: _show_local_page(
                tile, folder, off, page_obj, on_play
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
        )
    )

    grid = ft.ResponsiveRow(spacing=12, run_spacing=12)
    for i, v in enumerate(folder.videos[offset:end]):
        card = _build_video_card(v, offset + i, on_play, page_obj)
        wrapper = ft.Container(
            content=card, col={"xs": 4, "sm": 3, "md": 2, "lg": 2}, padding=4
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
                        0.12, AppColors.PRIMARY
                    )
                },
                padding=15,
                shape=ft.RoundedRectangleBorder(radius=10),
                side={
                    ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY),
                    ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY),
                },
            ),
            on_click=lambda e, off=end: _show_local_page(
                tile, folder, off, page_obj, on_play
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
                    width=60, height=60, stroke_width=6, color=AppColors.PRIMARY
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
        )
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
        )
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
        )
    )


def _render_folder_tiles(
    target, folders, active_tiles, page_obj, on_play, custom_paths, on_remove_custom
):
    for folder in folders:
        should_expand = len(folders) == 1
        tile_controls = []

        # If this folder is one of the manually added custom paths, give the user an option to remove it
        if folder.path in custom_paths:
            remove_btn = ft.TextButton(
                "Remove Custom Folder",
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.ERROR,
                style=ft.ButtonStyle(color=ft.Colors.ERROR),
                on_click=lambda e, p=folder.path: page_obj.run_task(
                    on_remove_custom, p
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
                    ft.Container(content=card, col={"xs": 4, "sm": 3, "md": 2, "lg": 2})
                )

            tile_controls.append(
                ft.Container(
                    content=ft.Text(
                        LBL_SHOWING_RANGE.format(start=1, end=end, total=total),
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
                e, f, active_tiles, page_obj, on_play
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
                            0.12, AppColors.PRIMARY
                        )
                    },
                    padding=15,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    side={
                        ft.ControlState.DEFAULT: ft.Border.all(1.5, AppColors.PRIMARY),
                        ft.ControlState.FOCUSED: ft.Border.all(2, AppColors.PRIMARY),
                    },
                ),
                on_click=lambda e, t=exp_tile, f=folder: _show_local_page(
                    t, f, PAGE_SIZE, page_obj, on_play
                ),
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

        # If the tile was just opened, load the first page of content (accounting for the remove button if it exists)
        has_content = any(isinstance(c, ft.ResponsiveRow) for c in e.control.controls)
        if not has_content:
            _show_local_page(e.control, folder, 0, page_obj, on_play)

        with contextlib.suppress(Exception):
            e.control.update()


# --- Main Entry Point ---


def build_local_tab_content(
    target, page_obj, on_play, ad_service, liveliness, view_state, active_tiles
):
    """Build the local videos tab."""

    async def _scan_device():
        custom_paths = view_state.get("custom_local_paths", [])
        paths = await _get_scan_paths(custom_paths)
        return await asyncio.to_thread(scan_videos, paths)

    async def handle_remove_custom_path(path_to_remove):
        custom_paths = view_state.get("custom_local_paths", [])
        if path_to_remove in custom_paths:
            custom_paths.remove(path_to_remove)
            view_state["custom_local_paths"] = custom_paths
            try:
                # Modern Flet 1.0 architecture uses SharedPreferences service
                await ft.SharedPreferences().set("ktv_custom_video_paths", custom_paths)
            except Exception as e:
                logger.error(f"Failed to remove SharedPreferences: {e}")
            page_obj.run_task(scan_local)

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
            _render_permission_needed(
                target, lambda _: page_obj.run_task(request_and_scan)
            )
        elif not folders:
            _render_no_videos(target)
        else:
            custom_paths = view_state.get("custom_local_paths", [])
            _render_folder_tiles(
                target,
                folders,
                active_tiles,
                page_obj,
                on_play,
                custom_paths,
                handle_remove_custom_path,
            )

        page_obj.update()

    async def request_and_scan():
        # Phase 5: Load SharedPreferences safely inside the async execution loop
        if "custom_local_paths" not in view_state:
            try:
                saved = await ft.SharedPreferences().get("ktv_custom_video_paths")
                view_state["custom_local_paths"] = (
                    saved if isinstance(saved, list) else []
                )
            except Exception as e:
                logger.warning(f"Failed to load SharedPreferences: {e}")
                view_state["custom_local_paths"] = []

        now = time.time()
        if (
            _scan_cache["folders"]
            and (now - _scan_cache["timestamp"]) < LOCAL_SCAN_CACHE_TTL
        ):
            view_state["local_folders"] = _scan_cache["folders"]
            view_state["local_permission_granted"] = True
            render()
            return

        await _ensure_services(page_obj)

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

    async def handle_add_folder(e):
        if _fp:
            path = await _fp.get_directory_path(dialog_title="Select Video Folder")
            if path:
                custom_paths = view_state.get("custom_local_paths", [])
                if path not in custom_paths:
                    custom_paths.append(path)
                    view_state["custom_local_paths"] = custom_paths
                    try:
                        # Save securely to Android/Desktop
                        await ft.SharedPreferences().set(
                            "ktv_custom_video_paths", custom_paths
                        )
                    except Exception as ex:
                        logger.error(f"Failed to save SharedPreferences: {ex}")

                # Trigger a fresh scan immediately after folder is added
                page_obj.run_task(scan_local)

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH, on_click=handle_refresh, tooltip=LBL_REFRESH_LOCAL
    )
    add_folder_btn = ft.IconButton(
        icon=ft.Icons.CREATE_NEW_FOLDER,
        on_click=handle_add_folder,
        tooltip="Add Folder Manually",
    )

    actions_row = ft.Row([add_folder_btn, refresh_btn], spacing=0)

    header = ft.Row(
        [ft.Text(LBL_LOCAL_VIDEOS, size=20, weight=ft.FontWeight.BOLD), actions_row],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    target.controls.append(header)
    page_obj.run_task(request_and_scan)
