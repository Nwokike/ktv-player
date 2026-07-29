"""LoadingState — a centered progress ring + label, for in-screen waits.

Plain function (not @ft.component) — no hooks needed, testable without
a renderer context.
"""

import flet as ft
from flet import Control

_DEFAULT_LABEL = "Loading..."
_CENTER = ft.Alignment(0.0, 0.0)


def LoadingState(label: str | None = None) -> Control:
    return ft.Container(
        alignment=_CENTER,
        expand=True,
        content=ft.Column(
            controls=[
                ft.ProgressRing(),
                ft.Text(label or _DEFAULT_LABEL),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )
