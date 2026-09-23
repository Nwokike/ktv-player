"""LoadingState — a Shimmer skeleton + label, for in-screen waits.

The shimmer previews the shape of what is coming (card blocks matching the
channel grid) instead of a bare spinner — a loading screen that looks like
the content is understood as faster, and the placeholders set up the
layout the user is about to see.

Plain function (not @ft.component) — no hooks needed, testable without
a renderer context.
"""

import flet as ft
from flet import Control

_DEFAULT_LABEL = "Loading..."
_CENTER = ft.Alignment(0.0, 0.0)
_SKELETON_WIDTH = 360
_SKELETON_HEIGHT = 96
# Page-independent colors (context-free construction); ON_SURFACE works on
# both themes because the shimmer sits on the page background.
_BASE = ft.Colors.with_opacity(0.10, ft.Colors.ON_SURFACE)
_HIGHLIGHT = ft.Colors.with_opacity(0.24, ft.Colors.ON_SURFACE)


def LoadingState(label: str | None = None) -> Control:
    skeleton_cards = [
        ft.Container(
            width=_SKELETON_WIDTH,
            height=_SKELETON_HEIGHT,
            border_radius=16,
            bgcolor=_BASE,
        )
        for _ in range(3)
    ]
    return ft.Container(
        alignment=_CENTER,
        expand=True,
        content=ft.Column(
            controls=[
                ft.Shimmer(
                    base_color=_BASE,
                    highlight_color=_HIGHLIGHT,
                    period=1400,
                    content=ft.Column(controls=skeleton_cards, spacing=12),
                ),
                ft.Text(label or _DEFAULT_LABEL, size=12, color=_HIGHLIGHT),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
        ),
    )
