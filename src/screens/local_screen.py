"""LocalScreen — device video scanner with folder expansion tiles."""

import asyncio
import json
import logging

import flet as ft
from flet import Control

logger = logging.getLogger("LocalScreen")

# How long to wait for the user to answer Android's delete-consent dialog.
_CONSENT_WAIT_POLLS = 40  # 40 x 0.5s = 20s
_CONSENT_POLL_INTERVAL = 0.5

import contextlib

import anyio

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


async def _resolve_storage_paths(sp) -> list[str]:
    """Accessible storage paths from a StoragePaths service + defaults.

    Module-level (testable) core of the per-mount singleton wrapper below.
    Merge, never replace: on Windows StoragePaths answers with just
    Downloads, and returning early skipped get_default_scan_paths() — the
    only place Videos/Desktop are listed.
    """
    paths = []
    if sp is not None:
        downloads = await sp.get_downloads_directory()
        if downloads:
            paths.append(downloads)
            logger.info("StoragePaths downloads: %s", downloads)
        try:
            ext = await sp.get_external_storage_directory()
            if ext and ext not in paths:
                paths.append(ext)
                logger.info("StoragePaths external: %s", ext)
        except Exception:
            pass
        try:
            exts = await sp.get_external_storage_directories()
            if exts:
                for e in exts:
                    if e not in paths:
                        paths.append(e)
                        logger.info("StoragePaths external_multi: %s", e)
        except Exception:
            pass

    # get_default_scan_paths() existence-checks at the source; re-checking
    # here would drop mocked/test paths and race deletions. Merge as-is.
    for extra in get_default_scan_paths():
        if extra and extra not in paths:
            paths.append(extra)
    if paths:
        return paths
    # Fallback to default paths (works on desktop)
    return get_default_scan_paths()


async def _get_storage_paths(sp=None) -> list[str]:
    """Module-level entry kept for tests: resolves with an optional service
    (None = defaults only). The component uses per-mount singletons."""
    if sp is None:
        try:
            from flet import StoragePaths

            sp = StoragePaths()
        except Exception as ex:
            logger.debug("StoragePaths unavailable: %s", ex)
            return get_default_scan_paths()
    try:
        return await _resolve_storage_paths(sp)
    except Exception as ex:
        logger.debug("StoragePaths unavailable: %s", ex)
        return get_default_scan_paths()


def _safe_task(coro_fn, *args, log_msg: str = "background task failed"):
    """Schedule a fire-and-forget coroutine with retrieved exceptions.

    Bare asyncio.create_task drops anything escaping the coroutine body
    (CancelledError, set_state-after-unmount, play failures) into "Task
    exception was never retrieved" — or total silence.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("No running loop for %s", log_msg)
        return None
    task = loop.create_task(coro_fn(*args))

    def _retrieve(t: asyncio.Task):
        try:
            if not t.cancelled():
                t.exception()
        except Exception:
            logger.debug(log_msg, exc_info=True)

    task.add_done_callback(_retrieve)
    return task


@ft.component
def LocalScreen() -> Control:
    controller = ft.use_context(ControllerMethodsCtx)

    folders, set_folders = ft.use_state([])
    custom_paths, set_custom_paths = ft.use_state([])
    is_scanning, set_is_scanning = ft.use_state(True)
    permission_state, set_permission_state = ft.use_state("unknown")
    consent_waiting, set_consent_waiting = ft.use_state(False)

    # Per-mount singletons: StoragePaths/SharedPreferences/FilePicker were
    # constructed per scan/prefs access (auto-registering a duplicate service
    # + page update each time, never unregistered). Capture page once per
    # mount and thread it explicitly — re-reading context.page inside slow
    # tasks can update the wrong page after navigation.
    mount = ft.use_ref({})
    scan_gen = ft.use_ref(0)
    prewarm_task = ft.use_ref(None)

    def _mount_refs():
        refs = mount.current
        if "page" not in refs:
            try:
                from flet import context

                refs["page"] = context.page
            except Exception:
                refs["page"] = None
        return refs

    def _storage_paths_service(page):
        refs = mount.current
        if refs.get("storage_paths") is None:
            try:
                from flet import StoragePaths

                refs["storage_paths"] = StoragePaths()
            except Exception:
                refs["storage_paths"] = False
        return refs.get("storage_paths") or None

    def _prefs_service(page):
        refs = mount.current
        if refs.get("prefs") is None:
            try:
                from flet import SharedPreferences

                refs["prefs"] = SharedPreferences()
            except Exception:
                refs["prefs"] = False
        return refs.get("prefs") or None

    def _picker_service(page):
        picker = getattr(page, "file_picker", None)
        if picker is not None:
            return picker
        # Defensive fallback if the boot singleton isn't registered
        # (e.g. in a fresh test page).
        try:
            from flet import FilePicker

            picker = FilePicker()
            page.services.append(picker)
            page.file_picker = picker
            with contextlib.suppress(Exception):
                page.update()
            return picker
        except Exception:
            return None

    async def _get_storage_paths(page) -> list[str]:
        """Accessible storage paths via the per-mount singleton service."""
        sp = _storage_paths_service(page)
        return await _resolve_storage_paths(sp)

    async def _get_custom_paths(page) -> list[str]:
        """Load custom paths from SharedPreferences (validated list-of-str)."""
        try:
            sp = _prefs_service(page)
            if sp is None:
                return []
            raw = await sp.get("ktv_custom_video_paths")
            if not raw:
                return []
            parsed = json.loads(raw)
            if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                return parsed
            logger.warning("Custom paths prefs are not a string list; ignoring")
        except Exception as ex:
            logger.debug("Custom paths load failed: %s", ex)
        return []

    async def _save_custom_paths(page, paths: list[str]):
        """Save custom paths to SharedPreferences."""
        try:
            sp = _prefs_service(page)
            if sp is None:
                return
            await sp.set("ktv_custom_video_paths", json.dumps(paths))
        except Exception as ex:
            logger.debug("Custom paths save failed: %s", ex)

    async def _prewarm(videos, page):
        # Android frame previews (no-op elsewhere); the grid upgrades itself
        # on completion via one page update.
        from services.video_thumbnails import (
            prewarm_thumbnails,
            purge_stale_thumbnails,
        )

        try:
            filled, _available = await prewarm_thumbnails(videos, page)
            if filled:
                logger.info("Prepared %d video thumbnails", filled)
            # Bounded cache: purge stale/orphan files after each prewarm so
            # the thumbnail dir cannot grow forever on TV boxes. Count-only
            # cap (~500 JPEGs) is documented at the purge function.
            with contextlib.suppress(Exception):
                await anyio.to_thread.run_sync(purge_stale_thumbnails)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Thumbnail prewarm failed", exc_info=True)

    async def _scan(page, *, background: bool = False) -> list:
        """Rescan the device.

        `background=True` refreshes the grid in place — used after a delete
        so the folder tree, its expansion state and the scroll position
        survive instead of flashing the full-screen loading state. A
        background failure NEVER clears the grid (log + keep old folders).
        Generation counter: overlapping scans queue on the lock, but only
        the latest applies its results (no scan stampede, last wins).
        """
        scan_gen.current += 1
        my_gen = scan_gen.current
        if not background:
            set_is_scanning(True)
        try:
            paths = list(await _get_storage_paths(page))
            custom = await _get_custom_paths(page)
            if my_gen == scan_gen.current:
                set_custom_paths(custom)
            for p in custom:
                if p not in paths:
                    paths.append(p)
            logger.info("Scanning %d paths: %s", len(paths), paths)
            result = await anyio.to_thread.run_sync(scan_videos, paths)
            if my_gen != scan_gen.current:
                logger.debug("Scan generation %d superseded, dropping", my_gen)
                return []
            logger.info("Scan found %d folders", len(result))
            set_folders(result)
            videos = [v for folder in result for v in folder.videos]
            if videos:
                old = prewarm_task.current
                if old is not None and not old.done():
                    old.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await old
                prewarm_task.current = _safe_task(
                    _prewarm, videos, page, log_msg="Thumbnail prewarm failed"
                )
            return result
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scan failed")
            if not background:
                set_folders([])
            return []
        finally:
            if not background:
                set_is_scanning(False)

    async def _on_mount():
        from services.permission_service import request_storage_permission

        refs = _mount_refs()
        page = refs.get("page")
        verdict = await request_storage_permission(page)
        set_permission_state(verdict)
        if verdict == "denied":
            set_is_scanning(False)
            return
        if verdict == "permanent":
            set_is_scanning(False)
            return
        await _scan(page)

    ft.on_mounted(_on_mount)

    def _on_unmount():
        task = prewarm_task.current
        prewarm_task.current = None
        if task is not None and not task.done():
            task.cancel()

    ft.on_unmounted(_on_unmount)

    def _refresh(e=None):
        from utils.notifications import notify

        refs = _mount_refs()
        notify("Rescanning device videos...")
        _safe_task(_scan, refs.get("page"), log_msg="Manual rescan failed")

    def _pick_folder(e=None):
        refs = _mount_refs()
        _safe_task(_pick_folder_async, refs.get("page"), log_msg="Folder pick failed")

    async def _pick_folder_async(page):
        from services.permission_service import (
            open_app_settings,
            request_storage_permission,
        )

        verdict = await request_storage_permission(page)
        set_permission_state(verdict)
        if verdict == "permanent":
            from utils.notifications import notify_warning

            notify_warning("Allow video access in Settings to add folders.")
            with contextlib.suppress(Exception):
                await open_app_settings(page)
            return
        if verdict != "granted":
            return

        picker = _picker_service(page)
        if picker is None:
            from utils.notifications import notify_warning

            notify_warning(ERR_FOLDER_PICK_FAILED)
            return
        try:
            path = await picker.get_directory_path(dialog_title="Select Video Folder")
        except asyncio.CancelledError:
            return
        except Exception as ex:
            if "session closed" in str(ex).lower():
                return  # App window was closed while picker dialog was open
            # Web raises FletUnsupportedPlatformException for directory pick.
            from utils.notifications import notify_warning

            try:
                if (
                    "unsupported" in str(ex).lower()
                    or "web" in str(getattr(page, "platform", "")).lower()
                ):
                    notify_warning("Folder picking isn't available on web.")
                else:
                    notify_warning(ERR_FOLDER_PICK_FAILED)
            except Exception:
                notify_warning(ERR_FOLDER_PICK_FAILED)
            logger.exception("Directory picker failed")
            return
        if not path:
            return
        from services.local_scanner import resolve_saf_path

        resolved_path = resolve_saf_path(path)
        if not resolved_path:
            from utils.notifications import notify_warning

            notify_warning(
                "That location can't be scanned (SD card / secondary volume)."
            )
            return
        paths = await _get_custom_paths(page)
        if resolved_path not in paths:
            paths.append(resolved_path)
            await _save_custom_paths(page, paths)
        await _scan(page)

    def on_play(path: str, title: str | None = None):
        _safe_task(
            controller.play_stream, path, title, log_msg=f"play failed for {path}"
        )

    def _open_search():
        if callable(getattr(controller, "open_search", None)):
            controller.open_search("local")

    refs_now = _mount_refs()
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

    if permission_state in ("denied", "permanent"):
        from services.permission_service import open_app_settings

        async def _grant(e=None):
            from services.permission_service import request_storage_permission

            refs = _mount_refs()
            verdict = await request_storage_permission(refs.get("page"))
            set_permission_state(verdict)
            if verdict == "granted":
                await _scan(refs.get("page"))
            elif verdict == "permanent":
                await open_app_settings(refs.get("page"))

        body = EmptyState(
            title="Video access needed",
            message=(
                "Allow access to videos to browse device files, or open "
                "Settings to enable it."
            ),
            action_label=(
                "Open Settings" if permission_state == "permanent" else "Grant Access"
            ),
            on_action=lambda e: _safe_task(_grant, log_msg="Permission grant failed"),
        )
        return ft.Stack(
            controls=[
                ft.Column(
                    controls=[header, body],
                    expand=True,
                    spacing=0,
                ),
            ],
            expand=True,
        )

    if is_scanning:
        return ft.Column(
            controls=[header, LoadingState(label=LBL_SCANNING_DEVICE)],
            expand=True,
            spacing=0,
        )

    async def _remove_custom_path(page, path_to_remove: str):
        custom = await _get_custom_paths(page)
        if path_to_remove in custom:
            custom.remove(path_to_remove)
            await _save_custom_paths(page, custom)
            await _scan(page)

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
        from components.banner_ad import build_banner_ad

        page = refs_now.get("page")
        mid_banner = ft.use_memo(lambda: build_banner_ad(page), [len(filtered_folders)])
        bottom_banner = ft.use_memo(lambda: build_banner_ad(page), [])

        async def _async_remove(page, p: str):
            await _remove_custom_path(page, p)

        def _on_video_long_press(v):
            refs = _mount_refs()
            _safe_task(_video_menu, v, refs.get("page"), log_msg="Video menu failed")

        async def _video_menu(v, page):
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

        async def _await_consent_delete(page, content_uri: str) -> bool:
            """Wait for the user to answer the system delete dialog.

            The dialog is a separate activity, so the answer cannot come back
            through a callback we own — the only reliable signal is the row
            disappearing from MediaStore. Progress is shown (not a silent
            20s wait); a decline ends the wait early with a message.
            """
            from services.local_scanner import media_store_exists
            from utils.notifications import notify

            set_consent_waiting(True)
            try:
                notify("Waiting for delete confirmation…")
                for _ in range(_CONSENT_WAIT_POLLS):
                    await asyncio.sleep(_CONSENT_POLL_INTERVAL)
                    exists = await anyio.to_thread.run_sync(
                        media_store_exists, content_uri
                    )
                    if exists is False:
                        return True
                    if exists is None:
                        # Could not query (activity gone, provider error) — that
                        # is not proof of a delete, so stop claiming one.
                        logger.info("Delete verification unavailable — using rescan")
                        return False
                return False
            finally:
                set_consent_waiting(False)

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
            consent_needed = False
            if v.content_uri:
                result = await anyio.to_thread.run_sync(
                    delete_media_store_video, v.content_uri
                )
                if result is True:
                    deleted = True
                elif result is None:
                    consent_needed = True
            if consent_needed and v.content_uri:
                # Android 11+ refuses deletes of media this app doesn't own
                # unless the user approves in the system dialog. The answer
                # arrives when the user taps Allow, not when the dialog
                # opens — so poll for it rather than deciding after a fixed
                # pause, which reported "Android kept a copy" for deletes
                # that had actually succeeded a second later.
                requested = await anyio.to_thread.run_sync(
                    request_media_store_delete, v.content_uri
                )
                if requested:
                    deleted = await _await_consent_delete(page, v.content_uri)
            if not deleted and v.path:
                deleted = await anyio.to_thread.run_sync(delete_local_file, v.path)
            if not deleted:
                notify_warning(
                    f"Could not delete {v.name} — Android may block deleting "
                    "files this app doesn't own"
                )
                return

            # Rescan FIRST, then report: MediaStore rows and the filesystem
            # can disagree, and the old "Deleted…" toast fired before the
            # rescan that proved it.
            remaining = await _scan(page, background=True)
            if any(
                item.path == v.path for folder in remaining for item in folder.videos
            ):
                notify_warning(
                    f"{v.name} is still in the library — Android kept a copy"
                )
                return
            notify(f"Deleted {v.name}")

        tiles: list[Control] = []
        for idx, folder in enumerate(filtered_folders):
            is_c = folder.path in custom_paths
            tiles.append(
                FolderExpansionTile(
                    folder=folder,
                    # Stable identity: a background rescan that removes or
                    # reorders a folder would otherwise shift every later
                    # tile's expansion/count state onto the wrong folder.
                    key=folder.path,
                    on_play=on_play,
                    is_custom=is_c,
                    on_remove_custom=lambda p: _safe_task(
                        _async_remove, page, p, log_msg="Remove custom path failed"
                    ),
                    on_long_press_video=_on_video_long_press,
                    on_video_menu=lambda v: _safe_task(
                        _video_menu, v, page, log_msg="Video menu failed"
                    ),
                )
            )
            # Insert banner ad after the 5th folder (index 4)
            if idx == 4 and len(filtered_folders) > 5 and mid_banner:
                mid_banner.key = "local-mid-banner"
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
            key="local-footer",
        )

        if bottom_banner:
            bottom_banner.key = "local-bottom-banner"
            tiles.append(bottom_banner)

        tiles.append(footer_hint)

        consent_bar = (
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.ProgressRing(width=16, height=16, stroke_width=2),
                        ft.Text(
                            "Waiting for delete confirmation…",
                            size=12,
                            color=ft.Colors.GREY_400,
                        ),
                    ],
                    spacing=8,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=ft.Padding(0, 8, 0, 8),
            )
            if consent_waiting
            else ft.Container(height=0, visible=False)
        )

        body = ft.Column(
            controls=[
                consent_bar,
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
                on_click=_pick_folder,
                bottom=80,
                right=12,
            ),
        ],
        expand=True,
    )
