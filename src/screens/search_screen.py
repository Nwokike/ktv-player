"""SearchScreen — dedicated search view with Live TV / Local Files mode toggle."""

from collections.abc import Callable

import anyio
import flet as ft
from flet import Control

from components.channel_grid import ChannelGrid
from components.empty_state import EmptyState
from core.theme import AppColors
from hooks.use_debounce import use_debounce


@ft.component
def SearchScreen(
    initial_mode: str = "tv",
    channels: list[dict] | None = None,
    favorites_set: set[str] | None = None,
    local_folders: list | None = None,
    on_play: Callable[..., None] | None = None,
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
    local_page, set_local_page = ft.use_state(0)
    # No screen-level liveliness subscription here: search tiles never read
    # the cache, and channel results own their dots per-card
    # (LivelinessChannelCard). The old unfiltered subscriber re-rendered the
    # whole screen on every verdict anywhere.

    # Reset local page when query or mode changes
    ft.use_effect(lambda: set_local_page(0), [debounced_query, mode])

    import logging as _logging

    _scan_log = _logging.getLogger(__name__)
    _scan_mounted = ft.use_ref(True)
    _scan_task = ft.use_ref(None)

    def _auto_scan_local():
        if not scanned_folders:
            import asyncio

            from services.local_scanner import get_default_scan_paths, scan_videos

            async def _do():
                try:
                    paths = get_default_scan_paths()
                    res = await anyio.to_thread.run_sync(scan_videos, paths)
                    if _scan_mounted.current:
                        set_scanned_folders(res)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _scan_log.debug("Search auto-scan failed", exc_info=True)

            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(_do())
                _scan_task.current = task

                def _log_failure(t):
                    if not t.cancelled() and t.exception():
                        _scan_log.debug(
                            "Search auto-scan task ended", exc_info=t.exception()
                        )

                task.add_done_callback(_log_failure)
            except RuntimeError:
                _scan_log.debug("Search auto-scan: no running loop")

    def _cancel_scan():
        _scan_mounted.current = False
        # Cancel the pooled thread read too: an orphaned scan would keep a
        # worker thread busy after the screen is gone.
        task = _scan_task.current
        if task is not None and not task.done():
            task.cancel()
        _scan_task.current = None

    # NOTE: cleanup is the 3rd use_effect arg (not a setup return).
    ft.use_effect(_auto_scan_local, [], _cancel_scan)

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
        border=ft.OutlineInputBorder(
            border_radius=14,
            side=ft.BorderSide(width=1, color=ft.Colors.TRANSPARENT),
        ),
        focused_border_color=AppColors.PRIMARY,
        focused_bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
        content_padding=ft.Padding.all(16),
        expand=True,
        on_change=lambda e: set_query(e.control.value),
        # Submit flushes immediately: the debounced value is the source of
        # truth for filtering, and waiting out the 250ms teaches users that
        # Enter does nothing.
        on_submit=lambda e: set_query(e.control.value),
    )

    search_button = ft.IconButton(
        icon=ft.Icons.SEARCH_ROUNDED,
        icon_color=AppColors.PRIMARY,
        tooltip="Search",
        # Flushes the CURRENT field text, not the debounced state: the
        # debounce already drives filtering, so this only needs to force
        # the latest keystrokes through immediately. `set_query(query)`
        # was a no-op (query is already the state being set).
        on_click=lambda e: set_query(search_field.value or query),
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
            filtered_tv = channels_list
        else:
            filtered_tv = [
                c
                for c in channels_list
                if q in c.get("name", "").lower()
                or q in c.get("group", "").lower()
                or q in c.get("country_code", "").lower()
            ]

        if not filtered_tv:
            body = EmptyState(
                title="No channels found",
                message=f'No live channels match "{debounced_query}".'
                if q
                else "No channels available.",
                action_label=None,
            )
        else:
            try:
                from flet import context as _grid_ctx

                _grid_page = _grid_ctx.page
            except Exception:
                _grid_page = None
            body = ChannelGrid(
                channels=filtered_tv,
                favorites_set=fav_set,
                on_play=on_play if callable(on_play) else (lambda u: None),
                on_toggle_favorite=on_toggle_favorite
                if callable(on_toggle_favorite)
                else (lambda u: None),
                page=_grid_page,
            )
    else:  # Local Files
        import os as _os

        filtered_files = []
        for folder in scanned_folders:
            vids = getattr(folder, "videos", [])
            for v in vids:
                name = getattr(v, "name", "") or ""
                path = getattr(v, "path", "") or ""
                # Basename/stem only: matching the full absolute path makes a
                # one-letter query ("c") match every C:\... file.
                stem = _os.path.splitext(_os.path.basename(path))[0]
                if not q or q in name.lower() or q in stem.lower():
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
            from components.channel_grid import _page_button
            from core.constants import PAGE_SIZE

            total_local_pages = max(
                1, (len(filtered_files) + PAGE_SIZE - 1) // PAGE_SIZE
            )
            current_local_page = min(local_page, total_local_pages - 1)

            start_idx = current_local_page * PAGE_SIZE
            end_idx = min(start_idx + PAGE_SIZE, len(filtered_files))
            visible_local_files = filtered_files[start_idx:end_idx]

            list_tiles = [
                ft.ListTile(
                    leading=ft.Icon(
                        ft.Icons.VIDEO_FILE_ROUNDED, color=AppColors.PRIMARY
                    ),
                    title=ft.Text(name, size=14, weight=ft.FontWeight.W_500),
                    subtitle=ft.Text(
                        _os.path.basename(path),
                        size=11,
                        color=AppColors.grey_dim(),
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    on_click=lambda e, p=path: (
                        on_play(p) if callable(on_play) else None
                    ),
                    key=path or None,
                )
                for name, path in visible_local_files
            ]

            local_controls: list[Control] = [
                ft.ListView(
                    controls=list_tiles,
                    expand=True,
                    spacing=4,
                )
            ]

            if total_local_pages > 1:
                prev_disabled = current_local_page == 0
                next_disabled = current_local_page >= total_local_pages - 1

                def _go_local_prev(e=None):
                    if not prev_disabled:
                        set_local_page(max(0, current_local_page - 1))

                def _go_local_next(e=None):
                    if not next_disabled:
                        set_local_page(
                            min(total_local_pages - 1, current_local_page + 1)
                        )

                local_controls.append(
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                _page_button(
                                    "Previous",
                                    ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                                    prev_disabled,
                                    _go_local_prev,
                                ),
                                ft.Text(
                                    f"Page {current_local_page + 1} of {total_local_pages}  ·  {len(filtered_files)} files",
                                    size=12,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.with_opacity(
                                        0.8, ft.Colors.ON_SURFACE
                                    ),
                                ),
                                _page_button(
                                    "Next",
                                    ft.Icons.ARROW_FORWARD_IOS_ROUNDED,
                                    next_disabled,
                                    _go_local_next,
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=16,
                        ),
                        padding=ft.Padding(0, 16, 0, 24),
                    )
                )

            body = ft.Column(
                controls=local_controls,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                # Key swap resets scroll offset on page flip (same fix as grid).
                key=f"local-search-{current_local_page}-{len(filtered_files)}",
            )

    from components.banner_ad import build_banner_ad

    try:
        from flet import context as _banner_ctx

        _banner_page = _banner_ctx.page
    except Exception:
        _banner_page = None
    # Memoized per mount: the old per-render build re-created a native ad
    # view on every liveliness tick.
    search_banner = ft.use_memo(lambda: build_banner_ad(_banner_page), [])

    column_controls = [header]
    if search_banner:
        column_controls.append(search_banner)
    column_controls.append(body)

    return ft.Container(
        expand=True,
        content=ft.Column(
            controls=column_controls,
            expand=True,
            spacing=0,
        ),
    )
