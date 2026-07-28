"""M1 placeholder for the four dashboard screens.

Real implementations: Home (M2), Search (M3), Local (M3),
Settings (M4). The placeholder exists so AppShell's NavigationBar can
route to all four destinations during M1 without crashing. Each tab shows
the destination name plus the milestone it lands in, so dev/test runs
make the in-progress status obvious.
"""

import flet as ft
from flet.controls.control import Control

_MILESTONE_BY_NAME = {
    "Home": "M2",
    "Search": "M3",
    "Local": "M3",
    "Settings": "M4",
}


def PlaceholderScreen(name: str = "Unknown", key=None) -> Control:
    milestone = _MILESTONE_BY_NAME.get(name, "?")
    return ft.Container(
        key=key,
        expand=True,
        alignment=ft.Alignment(0.0, 0.0),
        content=ft.Column(
            controls=[
                ft.Icon(ft.Icons.CONSTRUCTION, size=64),
                ft.Text(
                    f"{name} screen",
                    size=24,
                    weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    f"Lands in milestone {milestone}.",
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    size=13,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )
