"""EmptyState — centered icon + title + optional message + optional action button.

Plain function (not @ft.component) — no hooks needed, testable without
a renderer context.
"""

from collections.abc import Callable

import flet as ft
from flet import Control


def EmptyState(
    title: str,
    message: str = "",
    action_label: str | None = None,
    on_action: Callable | None = None,
    icon: ft.IconData = ft.Icons.INFO_OUTLINE,
    autofocus_action: bool = False,
) -> Control:
    items = [
        ft.Icon(icon, size=64),
        ft.Text(
            title, size=20, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER
        ),
    ]
    if message:
        items.append(
            ft.Text(
                message,
                size=14,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
                width=300,
            )
        )
    if action_label and on_action:
        items.append(
            ft.FilledButton(
                content=ft.Text(action_label),
                on_click=on_action,
                autofocus=autofocus_action,
            )
        )
    return ft.Container(
        expand=True,
        alignment=ft.Alignment(0.0, 0.0),
        content=ft.Column(
            items,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )
