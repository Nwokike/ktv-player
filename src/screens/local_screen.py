"""LocalScreen — device video scanner with folder expansion tiles."""

import asyncio
import logging

import flet as ft
from flet import Control

logger = logging.getLogger("LocalScreen")

# One LocalScreen is mounted at a time, but its build function re-runs on
# every state change — a closure variable would be recreated each time, so
# these two guards live at module scope. Scans serialize (the last one wins,
# none overlap) and thumbnail prewarming is cancelled rather than leaked.
_SCAN_LOCK = asyncio.Lock()
# How long to wait for the user to answer Android's delete-consent dialog.
_CONSENT_WAIT_POLLS = 20
_prewarm_task: asyncio.Task | None = None

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

    async def _prewarm(videos):
        # Android frame previews (no-op elsewhere); the grid upgrades itself
        # on completion via one page update.
        from flet import context

        from services.video_thumbnails import prewarm_thumbnails

        try:
            filled = await prewarm_thumbnails(videos, context.page)
            if filled:
                logger.info("Prepared %d video thumbnails", filled)
        except Exception:
            logger.debug("Thumbnail prewarm failed", exc_info=True)

    async def _scan(*, background: bool = False) -> list:
        """Rescan the device.

        `background=True` refreshes the grid in place — used after a delete
        so the folder tree, its expansion state and the scroll position
        survive instead of flashing the full-screen loading state.
        """
        if not background:
            set_is_scanning(True)
        try:
            async with _SCAN_LOCK:
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
                videos = [v for folder in result for v in folder.videos]
                if videos:
                    global _prewarm_task
                    if _prewarm_task is not None and not _prewarm_task.done():
                        _prewarm_task.cancel()
                    _prewarm_task = asyncio.create_task(_prewarm(videos))
                return result
        except Exception:
            logger.exception("Scan failed")
            set_folders([])
            return []
        finally:
            if not background:
                set_is_scanning(False)

    async def _on_mount():
        from flet import context

        from services.permission_service import request_storage_permission

        await request_storage_permission(context.page)
        await _scan()

    ft.on_mounted(_on_mount)

    def _refresh(e=None):
        from utils.notifications import notify

        notify("Rescanning device videos...")
        asyncio.create_task(_scan())

    def _pick_folder(e=None):
        asyncio.create_task(_pick_folder_async())

    async def _pick_folder_async():
        from flet import context

        from services.permission_service import request_storage_permission

        await request_storage_permission(context.page)

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
            from services.local_scanner import resolve_saf_path

            resolved_path = resolve_saf_path(path)
            paths = await _get_custom_paths()
            if resolved_path not in paths:
                paths.append(resolved_path)
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
        on_version_click=lambda: (
            controller.open_version_dialog()
            if callable(getattr(controller, "open_version_dialog", None))
            else None
        ),
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

        from flet import context

        from components.banner_ad import build_banner_ad

        page = context.page

        def _on_video_long_press(v):
            asyncio.create_task(_video_menu(v))

        async def _video_menu(v):
            page = context.page

            async def _play(e=None):
                page.pop_dialog()
                on_play(v.path)

            async def _delete(e=None):
                page.pop_dialog()
                await _delete_video(v, page)

            async def _cancel(e=None):
                page.pop_dialog()

            page.show_dialog(
                ft.AlertDialog(
                    title=ft.Text(v.name, size=15, weight=ft.FontWeight.BOLD),
                    content=ft.Text(
                        "Play this video, or delete it from the device?",
                        size=12,
                    ),
                    actions=[
                        ft.TextButton("Play", on_click=_play),
                        ft.TextButton(
                            "Delete",
                            icon=ft.Icons.DELETE_OUTLINE,
                            style=ft.ButtonStyle(color=ft.Colors.RED_400),
                            on_click=_delete,
                        ),
                        ft.TextButton("Cancel", on_click=_cancel),
                    ],
                )
            )

        async def _await_consent_delete(content_uri: str) -> bool:
            """Wait for the user to answer the system delete dialog.

            The dialog is a separate activity, so the answer cannot come back
            through a callback we own — the only reliable signal is the row
            disappearing from MediaStore. Polled for 20s, which covers a
            deliberate read-and-tap, and a decline simply ends the wait.
            """
            from services.local_scanner import media_store_exists

            for _ in range(_CONSENT_WAIT_POLLS):
                await asyncio.sleep(1.0)
                exists = await asyncio.to_thread(media_store_exists, content_uri)
                if exists is False:
                    return True
                if exists is None:
                    # Could not query (activity gone, provider error) — that
                    # is not proof of a delete, so stop claiming one.
                    logger.info("Delete verification unavailable — using rescan")
                    return False
            return False

        async def _delete_video(v, page):
            from services.local_scanner import (
                delete_local_file,
                delete_media_store_video,
                request_media_store_delete,
            )
            from utils.notifications import notify, notify_warning

            # MediaStore is what the scanner reads — deleting only the file
            # left the row (and the card) in place on Android.
            deleted = False
            if v.content_uri:
                deleted = await asyncio.to_thread(
                    delete_media_store_video, v.content_uri
                )
            if not deleted and v.content_uri:
                # Android 11+ refuses deletes of media this app doesn't own
                # unless the user approves in the system dialog. The answer
                # arrives when the user taps Allow, not when the dialog
                # opens — so poll for it rather than deciding after a fixed
                # pause, which reported "Android kept a copy" for deletes
                # that had actually succeeded a second later.
                requested = await asyncio.to_thread(
                    request_media_store_delete, v.content_uri
                )
                if requested:
                    deleted = await _await_consent_delete(v.content_uri)
            if not deleted and v.path:
                deleted = await asyncio.to_thread(delete_local_file, v.path)
            if not deleted:
                notify_warning(
                    f"Could not delete {v.name} — Android may block deleting "
                    "files this app doesn't own"
                )
                return

            # Rescan FIRST, then report: MediaStore rows and the filesystem
            # can disagree, and the old "Deleted…" toast fired before the
            # rescan that proved it.
            remaining = await _scan(background=True)
            if any(
                item.path == v.path for folder in remaining for item in folder.videos
            ):
                notify_warning(
                    f"{v.name} is still in the library — Android kept a copy"
                )
                return
            notify(f"Deleted {v.name}")

        tiles: list[Control] = []
        for idx, f in enumerate(filtered_folders):
            is_c = f.path in custom_paths
            tiles.append(
                FolderExpansionTile(
                    folder=f,
                    # Stable identity: a background rescan that removes or
                    # reorders a folder would otherwise shift every later
                    # tile's expansion/count state onto the wrong folder.
                    key=f.path,
                    on_play=on_play,
                    is_custom=is_c,
                    on_remove_custom=lambda p: asyncio.create_task(_async_remove(p)),
                    on_long_press_video=_on_video_long_press,
                    on_video_menu=lambda v: asyncio.create_task(_video_menu(v)),
                )
            )
            # Insert banner ad after the 5th folder (index 4)
            if idx == 4 and len(filtered_folders) > 5:
                mid_banner = build_banner_ad(page)
                if mid_banner:
                    tiles.append(mid_banner)

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

        banner = build_banner_ad(page)
        if banner:
            tiles.append(banner)

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
