"""LocalScreen — device video scanner with folder expansion tiles."""

import asyncio
import logging

import flet as ft
from flet import Control

logger = logging.getLogger("LocalScreen")

from app_next.components.empty_state import EmptyState
from app_next.components.folder_expansion_tile import FolderExpansionTile
from app_next.components.header import Header
from app_next.components.loading_state import LoadingState
from app_next.state.controller_ctx import ControllerMethodsCtx
from core.constants import (
    ERR_FOLDER_PICK_FAILED,
    LBL_ADD_FOLDER,
    LBL_LOCAL_FOOTER_HINT,
    LBL_LOCAL_SEARCH_HINT,
    LBL_NO_LOCAL_VIDEOS,
    LBL_NO_LOCAL_VIDEOS_HINT,
    LBL_SCAN_AGAIN,
    LBL_SCANNING_DEVICE,
)
from services.local_scanner import get_default_scan_paths, scan_videos


async def _get_storage_paths() -> list[str]:
    """Get accessible storage paths. Uses Flet's StoragePaths on Android
    (which returns real filesystem paths), falls back to hardcoded paths on desktop."""
    try:
        from flet import StoragePaths

        sp = StoragePaths()
        paths = []

        # get_downloads_directory works on Android and returns a real path
        downloads = await sp.get_downloads_directory()
        if downloads:
            paths.append(downloads)
            logger.info("StoragePaths downloads: %s", downloads)

        # get_external_storage_directory returns the external root on Android
        try:
            ext = await sp.get_external_storage_directory()
            if ext and ext not in paths:
                paths.append(ext)
                logger.info("StoragePaths external: %s", ext)
        except Exception:
            pass

        # get_external_storage_directories returns SD card paths etc.
        try:
            exts = await sp.get_external_storage_directories()
            if exts:
                for e in exts:
                    if e not in paths:
                        paths.append(e)
                        logger.info("StoragePaths external_multi: %s", e)
        except Exception:
            pass

        if paths:
            return paths
    except Exception as ex:
        logger.debug("StoragePaths unavailable: %s", ex)

    # Fallback to default paths (works on desktop)
    return get_default_scan_paths()


@ft.component
def LocalScreen() -> Control:
    controller = ft.use_context(ControllerMethodsCtx)

    folders, set_folders = ft.use_state([])
    is_scanning, set_is_scanning = ft.use_state(True)
    search_query, set_search_query = ft.use_state("")

    async def _get_custom_paths() -> list[str]:
        """Load custom paths from SharedPreferences."""
        try:
            import json

            from flet import SharedPreferences

            sp = SharedPreferences()
            raw = await sp.get("ktv_custom_video_paths")
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return []

    async def _save_custom_paths(paths: list[str]):
        """Save custom paths to SharedPreferences."""
        try:
            import json

            from flet import SharedPreferences

            sp = SharedPreferences()
            await sp.set("ktv_custom_video_paths", json.dumps(paths))
        except Exception:
            pass

    async def _scan():
        set_is_scanning(True)
        try:
            paths = list(await _get_storage_paths())
            custom = await _get_custom_paths()
            for p in custom:
                if p not in paths:
                    paths.append(p)
            logger.info("Scanning %d paths: %s", len(paths), paths)
            result = await asyncio.to_thread(scan_videos, paths)
            logger.info("Scan found %d folders", len(result))
            set_folders(result)
        except Exception:
            logger.exception("Scan failed")
            set_folders([])
        finally:
            set_is_scanning(False)

    ft.on_mounted(_scan)

    def _refresh(e=None):
        asyncio.create_task(_scan())

    def _pick_folder(e=None):
        asyncio.create_task(_pick_folder_async())

    async def _pick_folder_async():
        # Use the singleton FilePicker registered in AppController.init()
        # so it works on Android (where inline FilePicker() loses the
        # Service registration). Verified:
        # .venv/controls/services/file_picker.py:215 — async def
        # get_directory_path(dialog_title=None, initial_directory=None)
        # -> Optional[str].
        from flet import context

        picker = getattr(context.page, "file_picker", None)
        if picker is None:
            # Defensive fallback if for some reason the singleton isn't
            # registered (e.g. in a fresh test page).
            from flet import FilePicker

            picker = FilePicker()
            context.page.services.append(picker)
            context.page.file_picker = picker
        try:
            path = await picker.get_directory_path(dialog_title="Select Video Folder")
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Directory picker failed")
            from app_next.utils.notifications import notify_warning

            notify_warning(ERR_FOLDER_PICK_FAILED)
            return
        if path:
            paths = await _get_custom_paths()
            if path not in paths:
                paths.append(path)
                await _save_custom_paths(paths)
            await _scan()

    def on_play(path: str):
        asyncio.create_task(controller.play_stream(path, None))

    header = Header(
        search_value=search_query,
        search_hint=LBL_LOCAL_SEARCH_HINT,
        on_search_change=set_search_query,
        on_add_content=_pick_folder,
        add_tooltip=LBL_ADD_FOLDER,
        on_refresh=_refresh,
    )

    if is_scanning:
        return ft.Column(
            controls=[header, LoadingState(label=LBL_SCANNING_DEVICE)],
            expand=True,
            spacing=0,
        )

    # Filter folders and files based on search query
    filtered_folders = []
    q = search_query.strip().lower()
    if not q:
        filtered_folders = folders
    else:
        for f in folders:
            matching_files = [
                v for v in f.videos if q in v.name.lower() or q in v.path.lower()
            ]
            if q in f.name.lower() or matching_files:
                from services.local_scanner import VideoFolder

                filtered_folders.append(
                    VideoFolder(
                        name=f.name,
                        path=f.path,
                        videos=matching_files
                        if not q in f.name.lower()
                        else f.videos,
                    )
                )

    if not filtered_folders:
        body = ft.Container(
            expand=True,
            content=ft.Column(
                controls=[
                    EmptyState(
                        title=LBL_NO_LOCAL_VIDEOS,
                        message=LBL_NO_LOCAL_VIDEOS_HINT,
                        action_label=LBL_SCAN_AGAIN,
                        on_action=_refresh,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )
    else:
        tiles: list[Control] = [
            FolderExpansionTile(folder=f, on_play=on_play) for f in filtered_folders
        ]
        footer_hint = ft.Container(
            content=ft.Text(
                LBL_LOCAL_FOOTER_HINT,
                size=12,
                color=ft.Colors.GREY_400,
                text_align=ft.TextAlign.CENTER,
            ),
            padding=ft.Padding(16, 16, 16, 24),
            alignment=ft.Alignment.CENTER,
        )
        tiles.append(footer_hint)

        body = ft.Column(
            controls=[
                ft.ListView(
                    controls=tiles,
                    expand=True,
                    spacing=4,
                    build_controls_on_demand=True,
                ),
            ],
            expand=True,
            spacing=0,
        )

    # Wrap body in Stack so the FAB can float above it. The FAB action
    # is the same +pick_folder used by Header on_add_content.
    return ft.Stack(
        controls=[
            ft.Column(
                controls=[header, body],
                expand=True,
                spacing=0,
            ),
            ft.FloatingActionButton(
                content=ft.Icon(ft.Icons.ADD),
                mini=True,
                tooltip=LBL_ADD_FOLDER,
                on_click=lambda e: _pick_folder(),
                bottom=80,
                right=12,
            ),
        ],
        expand=True,
    )
