"""LocalScreen — device video scanner with folder expansion tiles."""

import asyncio

import flet as ft
from flet.controls.control import Control

from app_next.components.empty_state import EmptyState
from app_next.components.folder_expansion_tile import FolderExpansionTile
from app_next.components.header import Header
from app_next.components.loading_state import LoadingState
from app_next.state.controller_ctx import ControllerMethodsCtx
from services.local_scanner import get_default_scan_paths, scan_videos


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

            from flet.controls.services.shared_preferences import SharedPreferences

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

            from flet.controls.services.shared_preferences import SharedPreferences

            sp = SharedPreferences()
            await sp.set("ktv_custom_video_paths", json.dumps(paths))
        except Exception:
            pass

    async def _scan():
        set_is_scanning(True)
        try:
            paths = list(get_default_scan_paths())
            custom = await _get_custom_paths()
            for p in custom:
                if p not in paths:
                    paths.append(p)
            result = await asyncio.to_thread(scan_videos, paths)
            set_folders(result)
        except Exception:
            set_folders([])
        finally:
            set_is_scanning(False)

    ft.on_mounted(_scan)

    async def _refresh(e=None):
        await _scan()

    async def _pick_folder(e=None):
        from flet.controls.services.file_picker import FilePicker

        from core.theme import AppColors

        fp = FilePicker()
        try:
            path = await fp.get_directory_path(dialog_title="Select Video Folder")
        except asyncio.CancelledError:
            return
        except Exception:
            from flet.controls.context import context

            try:
                context.page.show_dialog(
                    ft.SnackBar(
                        ft.Text("Failed to pick folder"), bgcolor=AppColors.WARNING
                    )
                )
            except Exception:
                pass
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
        search_hint="Search local videos...",
        on_search_change=set_search_query,
        on_add_content=_pick_folder,
        add_tooltip="Add Folder",
        on_refresh=_refresh,
    )

    if is_scanning:
        return ft.Column(
            controls=[header, LoadingState(label="Scanning device storage...")],
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
                v for v in f.videos if q in v.title.lower() or q in v.path.lower()
            ]
            if q in f.folder_name.lower() or matching_files:
                from services.local_scanner import VideoFolder

                filtered_folders.append(
                    VideoFolder(
                        folder_name=f.folder_name,
                        folder_path=f.folder_path,
                        videos=matching_files
                        if not q in f.folder_name.lower()
                        else f.videos,
                    )
                )

    if not filtered_folders:
        body = ft.Container(
            expand=True,
            content=ft.Column(
                controls=[
                    EmptyState(
                        title="No local videos found",
                        message="Tap the + button at the top to add a video folder.",
                        action_label="Scan Again",
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
                "If you want to add more folders, click the + sign at the top",
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

    return ft.Column(
        controls=[
            header,
            body,
        ],
        expand=True,
        spacing=0,
    )
