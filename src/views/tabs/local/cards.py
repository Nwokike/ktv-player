"""UI card builders for local video files."""

import flet as ft

from core.theme import AppColors
from services.local_scanner import _format_size


def _build_video_card(video, idx, on_play, page_obj):
    card = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            width=8,
                            height=8,
                            border_radius=4,
                            bgcolor=AppColors.SUCCESS,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
                ft.Icon(ft.Icons.MOVIE_OUTLINED, size=38, color=AppColors.PRIMARY),
                ft.Text(
                    video.name,
                    size=12,
                    weight=ft.FontWeight.W_500,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    _format_size(video.size),
                    size=10,
                    color=AppColors.GREY_DIM,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
        padding=12,
        border_radius=16,
        bgcolor=AppColors.get_surface(page_obj)
        if page_obj
        else ft.Colors.with_opacity(0.04, ft.Colors.ON_SURFACE),
        border=ft.Border.all(
            0.5,
            AppColors.get_border_color(page_obj)
            if page_obj
            else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
        ),
        ink=True,
        height=140,
        key=f"local_vid_{idx}",
        on_click=lambda e, path=video.path: page_obj.run_task(on_play, path),
    )
    card.tab_index = idx + 10

    return card
