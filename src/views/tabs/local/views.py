"""View builder and main tab controller for local video tab."""

import asyncio
import logging
import time

import flet as ft

from core.constants import LBL_LOCAL_VIDEOS, LBL_REFRESH_LOCAL, LOCAL_SCAN_CACHE_TTL
from services.local_scanner import scan_videos
from views.tabs.local.renderers import (
    _render_folder_tiles,
    _render_no_videos,
    _render_permission_needed,
    _render_scanning,
)
from views.tabs.local.services import (
    _ensure_services,
    _fp,
    _get_scan_paths,
    _request_storage_permission,
)

logger = logging.getLogger(__name__)

_scan_cache = {"folders": [], "timestamp": 0.0}


def build_local_tab_content(
    target,
    page_obj,
    on_play,
    ad_service,
    liveliness,
    view_state,
    active_tiles,
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
                await ft.SharedPreferences().set("ktv_custom_video_paths", custom_paths)
            except Exception:
                logger.exception("Failed to remove SharedPreferences")
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
                target,
                lambda _: page_obj.run_task(request_and_scan),
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
        if "custom_local_paths" not in view_state:
            try:
                saved = await ft.SharedPreferences().get("ktv_custom_video_paths")
                view_state["custom_local_paths"] = (
                    saved if isinstance(saved, list) else []
                )
            except Exception:
                logger.warning("Failed to load SharedPreferences", exc_info=True)
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
                        await ft.SharedPreferences().set(
                            "ktv_custom_video_paths",
                            custom_paths,
                        )
                    except Exception:
                        logger.exception("Failed to save SharedPreferences")

                page_obj.run_task(scan_local)

    refresh_btn = ft.IconButton(
        icon=ft.Icons.REFRESH,
        on_click=handle_refresh,
        tooltip=LBL_REFRESH_LOCAL,
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
