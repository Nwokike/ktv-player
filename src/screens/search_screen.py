"""SearchScreen — dedicated search view with Live TV / Local Files mode toggle."""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.channel_card import ChannelCard
from components.empty_state import EmptyState
from core.theme import AppColors
from hooks.use_debounce import use_debounce


@ft.component
def SearchScreen(
    initial_mode: str = "tv",
    channels: list[dict] | None = None,
    favorites_set: set[str] | None = None,
    local_folders: list | None = None,
    on_play: Callable[[str], None] | None = None,
    on_toggle_favorite: Callable[[str], None] | None = None,
    on_back: Callable[[], None] | None = None,
) -> Control:
    mode, set_mode = ft.use_state(
        initial_mode if initial_mode in ("tv", "local") else "tv"
    )
    query, set_query = ft.use_state("")
    debounced_query = use_debounce(query, 250)
    scanned_folders, set_scanned_folders = ft.use_state(local_folders or [])
    channels_list = channels or []
    fav_set = favorites_set or set()
    _liveliness_version, set_liveliness_version = ft.use_state(0)
    pending_render = ft.use_ref(False)

    def _on_liveliness_change():
        if pending_render.current:
            return
        pending_render.current = True

        async def _flush():
            import asyncio

            await asyncio.sleep(0.5)
            pending_render.current = False
            set_liveliness_version(lambda v: v + 1)

        try:
            import asyncio

            loop = asyncio.get_running_loop()
            loop.create_task(_flush())
        except RuntimeError:
            pending_render.current = False
            set_liveliness_version(lambda v: v + 1)

    from services.liveliness import liveliness_cache

    ft.use_effect(lambda: liveliness_cache.set_on_change(_on_liveliness_change), [])

    def _auto_scan_local():
        if not scanned_folders:
            import asyncio

            from services.local_scanner import get_default_scan_paths, scan_videos

            async def _do():
                try:
                    paths = get_default_scan_paths()
                    res = await asyncio.to_thread(scan_videos, paths)
                    set_scanned_folders(res)
                except Exception:
                    pass

            asyncio.create_task(_do())

    ft.use_effect(_auto_scan_local, [])

    # --- Mode Toggle Switcher ---
    def _switch_mode(new_mode: str):
        set_mode(new_mode)

    tv_btn_bgcolor = AppColors.PRIMARY if mode == "tv" else ft.Colors.TRANSPARENT
    tv_btn_color = ft.Colors.WHITE if mode == "tv" else AppColors.grey_dim()

    local_btn_bgcolor = AppColors.PRIMARY if mode == "local" else ft.Colors.TRANSPARENT
    local_btn_color = ft.Colors.WHITE if mode == "local" else AppColors.grey_dim()

    mode_switch_bar = ft.Container(
        padding=ft.Padding(4, 4, 4, 4),
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.ON_SURFACE)),
        content=ft.Row(
            controls=[
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.LIVE_TV_ROUNDED, size=16, color=tv_btn_color
                            ),
                            ft.Text(
                                "Channels",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=tv_btn_color,
                            ),
                        ],
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    bgcolor=tv_btn_bgcolor,
                    border_radius=8,
                    padding=ft.Padding(12, 6, 12, 6),
                    ink=True,
                    on_click=lambda e: _switch_mode("tv"),
                ),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.FOLDER_ROUNDED, size=16, color=local_btn_color
                            ),
                            ft.Text(
                                "Local Files",
                                size=12,
                                weight=ft.FontWeight.BOLD,
                                color=local_btn_color,
                            ),
                        ],
                        spacing=6,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    bgcolor=local_btn_bgcolor,
                    border_radius=8,
                    padding=ft.Padding(12, 6, 12, 6),
                    ink=True,
                    on_click=lambda e: _switch_mode("local"),
                ),
            ],
            spacing=4,
            tight=True,
        ),
    )

    search_field = ft.TextField(
        value=query,
        hint_text="Search TV channels or local videos...",
        autofocus=True,
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        border_color=ft.Colors.TRANSPARENT,
        focused_border_color=AppColors.PRIMARY,
        focused_bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
        border_radius=14,
        content_padding=16,
        expand=True,
        on_change=lambda e: set_query(e.control.value),
        on_submit=lambda e: set_query(e.control.value),
    )

    search_button = ft.IconButton(
        icon=ft.Icons.SEARCH_ROUNDED,
        icon_color=AppColors.PRIMARY,
        tooltip="Search",
        on_click=lambda e: set_query(search_field.value if search_field.value else ""),
    )

    back_button = ft.IconButton(
        icon=ft.Icons.ARROW_BACK_ROUNDED,
        tooltip="Back",
        on_click=lambda e: on_back() if callable(on_back) else None,
    )

    header = ft.Container(
        padding=ft.Padding(16, 16, 16, 12),
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        back_button,
                        ft.Text("Search", size=22, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        mode_switch_bar,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=8),
                ft.Row(
                    controls=[search_field, search_button],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=4,
        ),
    )

    # --- Filtering Logic ---
    q = debounced_query.strip().lower()

    if mode == "tv":
        if not q:
            filtered_tv = channels_list[:24]
        else:
            matches = [
                c
                for c in channels_list
                if q in c.get("name", "").lower()
                or q in c.get("group", "").lower()
                or q in c.get("country_code", "").lower()
            ]
            filtered_tv = matches[:24]

        def _seed_search_liveliness():
            if mode == "tv" and filtered_tv:
                from services.liveliness_checker import (
                    drain_queue,
                    enqueue_liveliness_check,
                )
                from services.logo_cache import enqueue_logo_download

                drain_queue()
                for ch in filtered_tv:
                    url = ch.get("url", "")
                    if url:
                        enqueue_liveliness_check(url)
                    logo = ch.get("logo") or ""
                    if logo and not logo.startswith("/"):
                        enqueue_logo_download(logo)

        ft.use_effect(_seed_search_liveliness, [debounced_query, mode])

        if not filtered_tv:
            body = EmptyState(
                title="No channels found",
                message=f'No live channels match "{debounced_query}".'
                if q
                else "No channels available.",
                action_label=None,
            )
        else:
            grid_cards = [
                ft.Container(
                    content=ChannelCard(
                        channel=ch,
                        is_favorite=ch.get("url", "") in fav_set,
                        liveliness_status=liveliness_cache.get(ch.get("url", "")),
                        on_play=on_play if callable(on_play) else (lambda u: None),
                        on_toggle_favorite=on_toggle_favorite
                        if callable(on_toggle_favorite)
                        else (lambda u: None),
                    ),
                    col={"xs": 6, "sm": 4, "md": 3, "lg": 2, "xl": 2},
                    padding=4,
                )
                for ch in filtered_tv
            ]
            body = ft.ListView(
                controls=[
                    ft.ResponsiveRow(
                        controls=grid_cards,
                        spacing=12,
                        run_spacing=12,
                    )
                ],
                expand=True,
                padding=ft.Padding(16, 8, 16, 24),
            )
    else:  # Local Files
        filtered_files = []
        for folder in scanned_folders:
            vids = getattr(folder, "videos", [])
            for v in vids:
                name = getattr(v, "name", "")
                path = getattr(v, "path", "")
                if not q or q in name.lower() or q in path.lower():
                    filtered_files.append((name, path))

        if not filtered_files:
            body = EmptyState(
                title="No local files found",
                message=f'No local video files match "{debounced_query}".'
                if q
                else "No local video files found on device.",
                action_label=None,
            )
        else:
            list_tiles = [
                ft.ListTile(
                    leading=ft.Icon(
                        ft.Icons.VIDEO_FILE_ROUNDED, color=AppColors.PRIMARY
                    ),
                    title=ft.Text(name, size=14, weight=ft.FontWeight.W_500),
                    subtitle=ft.Text(
                        path,
                        size=11,
                        color=AppColors.grey_dim(),
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    on_click=lambda e, p=path: (
                        on_play(p) if callable(on_play) else None
                    ),
                )
                for name, path in filtered_files[:24]
            ]
            body = ft.ListView(
                controls=list_tiles,
                expand=True,
                padding=ft.Padding(16, 8, 16, 24),
            )

    return ft.Container(
        expand=True,
        content=ft.Column(
            controls=[header, body],
            expand=True,
            spacing=0,
        ),
    )
