"""LocalScreen — device video scanner with folder expansion tiles."""

import asyncio
import logging

import flet as ft
from flet import Control

logger = logging.getLogger("LocalScreen")

from components.empty_state import EmptyState
from components.folder_expansion_tile import FolderExpansionTile
from components.header import Header
from components.loading_state import LoadingState
from core.constants import (
    ERR_FOLDER_PICK_FAILED,
    LBL_ADD_FOLDER,
    LBL_LOCAL_FOOTER_HINT,
    LBL_NO_LOCAL_VIDEOS,
    LBL_SCANNING_DEVICE,
)
from services.local_scanner import get_default_scan_paths, scan_videos
from state.controller_ctx import ControllerMethodsCtx


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
    custom_paths, set_custom_paths = ft.use_state([])
    is_scanning, set_is_scanning = ft.use_state(True)

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
            set_custom_paths(custom)
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
        from utils.notifications import notify

        notify("Rescanning device videos...")
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
        except Exception as ex:
            if "session closed" in str(ex).lower():
                return  # App window was closed while picker dialog was open
            logger.exception("Directory picker failed")
            from utils.notifications import notify_warning

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

    def _open_search():
        if callable(getattr(controller, "open_search", None)):
            controller.open_search("local")

    header = Header(
        on_search_click=_open_search,
        on_add_content=_pick_folder,
        on_refresh=_refresh,
        refresh_tooltip="Rescan Local Videos",
    )

    if is_scanning:
        return ft.Column(
            controls=[header, LoadingState(label=LBL_SCANNING_DEVICE)],
            expand=True,
            spacing=0,
        )

    async def _remove_custom_path(path_to_remove: str):
        custom = await _get_custom_paths()
        if path_to_remove in custom:
            custom.remove(path_to_remove)
            await _save_custom_paths(custom)
            await _scan()

    filtered_folders = folders

    if not filtered_folders:
        body = ft.Container(
            expand=True,
            content=ft.Column(
                controls=[
                    EmptyState(
                        title=LBL_NO_LOCAL_VIDEOS,
                        message="No video folders found. Tap the '+' icon above to add a custom video folder from your device.",
                        action_label="Add Video Folder",
                        on_action=_pick_folder,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )
    else:

        async def _async_remove(p: str):
            await _remove_custom_path(p)

        tiles: list[Control] = []
        for f in filtered_folders:
            is_c = f.path in custom_paths
            tiles.append(
                FolderExpansionTile(
                    folder=f,
                    on_play=on_play,
                    is_custom=is_c,
                    on_remove_custom=lambda p: asyncio.create_task(_async_remove(p)),
                )
            )

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
