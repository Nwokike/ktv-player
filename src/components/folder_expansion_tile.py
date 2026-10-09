"""FolderExpansionTile — expandable folder tile with incremental video loading.

@ft.component with use_state for expanded state and current page count.
When expanded, renders a wrapping Row of VideoCards (first PAGE_SIZE items)
plus a "Load more" button if there are more videos. Row(wrap=True) (not
GridView): the tile sits inside an outer ListView, and a scrollable GridView
with expand=True inside an unbounded Column is a layout hazard (flex in
unbounded viewport / competing scroll). A wrapping Row sizes itself to its
children and lets the outer ListView own all scrolling.
"""

from collections.abc import Callable

import flet as ft
from flet import Control

from components.video_card import VideoCard
from core.constants import PAGE_SIZE
from services.local_scanner import LocalVideo, VideoFolder


@ft.component
def FolderExpansionTile(
    folder: VideoFolder,
    on_play: Callable[..., None],
    is_custom: bool = False,
    on_remove_custom: Callable[[str], None] | None = None,
    on_long_press_video: Callable[[LocalVideo], None] | None = None,
    on_video_menu: Callable[[LocalVideo], None] | None = None,
) -> Control:
    expanded, set_expanded = ft.use_state(False)
    count, set_count = ft.use_state(PAGE_SIZE)

    def _expand(e):
        # Functional updaters: rapid double-taps before rebuild reuse stale
        # closure values and lose an increment/toggle.
        set_expanded(lambda prev: not prev)
        set_count(lambda prev: PAGE_SIZE if not expanded else prev)

    def _load_more(e):
        set_count(lambda prev: prev + PAGE_SIZE)

    visible_videos = folder.videos[:count]
    total = len(folder.videos)

    header_subtitle = folder.path if is_custom else f"{total} videos"
    header = ft.ListTile(
        title=ft.Text(f"{folder.name} ({total})", weight=ft.FontWeight.W_600),
        subtitle=ft.Text(header_subtitle, size=11, color=ft.Colors.GREY_400),
        trailing=ft.Icon(
            ft.Icons.EXPAND_MORE if not expanded else ft.Icons.EXPAND_LESS
        ),
        on_click=_expand,
    )

    if not expanded:
        return ft.Container(content=header, padding=ft.Padding.symmetric(horizontal=8))

    items = [header]

    if is_custom and on_remove_custom:
        remove_btn = ft.Container(
            content=ft.TextButton(
                "Remove Custom Folder",
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                style=ft.ButtonStyle(color=ft.Colors.RED_400),
                on_click=lambda _: on_remove_custom(folder.path),
            ),
            padding=ft.Padding.symmetric(horizontal=12),
        )
        items.append(remove_btn)

    if total == 0:
        items.append(
            ft.Container(
                content=ft.Text(
                    "Empty folder",
                    size=12,
                    color=ft.Colors.GREY_400,
                ),
                padding=ft.Padding.symmetric(horizontal=16, vertical=8),
            )
        )
    else:
        items.append(
            ft.Row(
                controls=[
                    ft.Container(
                        content=VideoCard(
                            v,
                            on_play=on_play,
                            on_long_press=on_long_press_video,
                            on_menu=on_video_menu,
                        ),
                        width=160,
                        padding=4,
                        key=v.path or None,
                    )
                    for v in visible_videos
                ],
                wrap=True,
                spacing=8,
                run_spacing=8,
            )
        )

    if count < total:
        remaining = total - count
        items.append(
            ft.Container(
                content=ft.OutlinedButton(
                    content=ft.Text(f"Load more ({remaining} remaining)"),
                    on_click=_load_more,
                ),
                alignment=ft.Alignment.CENTER,
                padding=ft.Padding.all(10),
            )
        )

    return ft.Container(
        content=ft.Column(items, spacing=4),
        padding=ft.Padding.symmetric(vertical=4),
    )
