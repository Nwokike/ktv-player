"""LocalScreen — device video scanner with folder expansion tiles."""

import asyncio

import flet as ft
from flet.controls.control import Control

from app_next.components.empty_state import EmptyState
from app_next.components.folder_expansion_tile import FolderExpansionTile
from app_next.components.loading_state import LoadingState
from app_next.state.controller_ctx import ControllerMethodsCtx
from services.local_scanner import get_default_scan_paths, scan_videos


@ft.component
def LocalScreen() -> Control:
    controller = ft.use_context(ControllerMethodsCtx)

    folders, set_folders = ft.use_state([])
    is_scanning, set_is_scanning = ft.use_state(True)

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

    async def _refresh(e):
        await _scan()

    async def _pick_folder(e):
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

    if is_scanning:
        return LoadingState(label="Scanning device storage...")

    if not folders:
        return ft.Container(
            expand=True,
            content=ft.Column(
                controls=[
                    EmptyState(
                        title="No local videos found",
                        message="Tap Scan to search your device for video files.",
                        action_label="Scan Again",
                        on_action=_refresh,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
        )

    tiles = [FolderExpansionTile(folder=f, on_play=on_play) for f in folders]
    return ft.Column(
        controls=[
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.FilledButton(
                            content=ft.Text("Scan Again"),
                            icon=ft.Icons.REFRESH,
                            on_click=_refresh,
                            autofocus=True,
                        ),
                        ft.FilledButton(
                            content=ft.Text("Add Folder"),
                            icon=ft.Icons.CREATE_NEW_FOLDER,
                            on_click=_pick_folder,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
                padding=ft.Padding(12, 8, 12, 4),
            ),
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
