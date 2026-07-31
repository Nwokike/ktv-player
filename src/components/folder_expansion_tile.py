"""FolderExpansionTile — expandable folder tile with incremental video loading.

@ft.component with use_state for expanded state and current page count.
When expanded, renders a GridView of VideoCards (first PAGE_SIZE items)
plus a "Load more" button if there are more videos.
"""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.video_card import VideoCard
from core.constants import PAGE_SIZE
from services.local_scanner import VideoFolder


@ft.component
def FolderExpansionTile(
    folder: VideoFolder,
    on_play: Callable[[str], None],
) -> Control:
    expanded, set_expanded = ft.use_state(False)
    count, set_count = ft.use_state(PAGE_SIZE)

    def _expand(e):
        set_expanded(not expanded)
        if not expanded:
            set_count(PAGE_SIZE)

    def _load_more(e):
        set_count(count + PAGE_SIZE)

    visible_videos = folder.videos[:count]
    total = len(folder.videos)

    header = ft.ListTile(
        title=ft.Text(f"{folder.name} ({folder.count})", weight=ft.FontWeight.W_600),
        trailing=ft.Icon(
            ft.Icons.EXPAND_MORE if not expanded else ft.Icons.EXPAND_LESS
        ),
        on_click=_expand,
    )

    if not expanded:
        return ft.Container(content=header, padding=ft.Padding.symmetric(horizontal=8))

    cards = [VideoCard(v, on_play=on_play) for v in visible_videos]
    grid = ft.GridView(
        controls=[
            ft.Container(
                content=card, col={"xs": 4, "sm": 3, "md": 2, "lg": 2}, padding=4
            )
            for card in cards
        ],
        runs_count=3,
        max_extent=160,
        child_aspect_ratio=0.75,
        spacing=8,
        run_spacing=8,
        expand=True,
        build_controls_on_demand=True,
    )

    items = [header, grid]

    if count < total:
        remaining = total - count
        items.append(
            ft.Container(
                content=ft.OutlinedButton(
                    content=ft.Text(f"Load more ({remaining} remaining)"),
                    on_click=_load_more,
                ),
                alignment=ft.Alignment.CENTER,
                padding=10,
            )
        )

    return ft.Container(
        content=ft.Column(items, spacing=4),
        padding=ft.Padding.symmetric(vertical=4),
    )
