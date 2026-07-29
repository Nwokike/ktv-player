"""OfflineFlow — retry / skip-to-offline surface shown when channels won't load.

Plain function (not @ft.component) — no hooks needed. Receives callbacks
for retry and skip actions; the parent component owns async + loading state.
"""

import flet as ft
from flet.controls.control import Control

from core.theme import AppColors


def OfflineFlow(on_retry, on_skip) -> Control:
    """Render a centered card with a Retry and a Skip-to-offline button.

    on_retry / on_skip are called with the click event.
    """
    return ft.Container(
        alignment=ft.Alignment(0.0, 0.0),
        expand=True,
        content=ft.Column(
            controls=[
                ft.Icon(ft.Icons.CLOUD_OFF, size=64, color=AppColors.grey_dim()),
                ft.Text(
                    "Can't connect to the channel directory.",
                    text_align=ft.TextAlign.CENTER,
                    size=16,
                ),
                ft.Text(
                    "You can retry, or continue in offline mode with your local videos.",
                    text_align=ft.TextAlign.CENTER,
                    size=13,
                    color=AppColors.grey_dim(),
                ),
                ft.FilledButton(
                    content=ft.Text("Retry Connection"),
                    icon=ft.Icons.REFRESH,
                    on_click=on_retry,
                ),
                ft.OutlinedButton(
                    content=ft.Text("Continue Offline"),
                    on_click=on_skip,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )
