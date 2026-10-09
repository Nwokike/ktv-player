"""RecentlyWatchedScreen — full vertical list of all watched streams."""

from collections.abc import Callable

import flet as ft
from flet import Control

from core.theme import AppColors
from utils.history import resolve_entry


def RecentlyWatchedScreen(
    history: list[dict | str],
    channels_map: dict[str, dict],
    on_play: Callable[..., None],
    on_back: Callable[[], None] | None = None,
    page=None,
) -> Control:
    """Body of the /recently-watched view (title-only rows; raw URLs are
    never rendered — stream URLs commonly contain user:pass@ credentials).

    The AppBar lives on the View (View(appbar=...), set by the caller) — not
    inside this Column, where it gets no route-integrated back behavior.
    on_back closes the overlay (empty-state CTA uses it too). page is an
    explicit prop (no context.page access: testable, no RuntimeError)."""

    def _make_card(entry: dict | str) -> Control | None:
        resolved = resolve_entry(entry, channels_map)
        if resolved is None:
            return None
        url, stored_title, title, logo_src = resolved

        return ft.Container(
            content=ft.Row(
                controls=[
                    ft.Image(
                        src=logo_src,
                        width=48,
                        height=48,
                        fit=ft.BoxFit.CONTAIN,
                        border_radius=8,
                        placeholder_src="/icon.png",
                        error_content=ft.Icon(ft.Icons.TV, size=22),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text(
                                title,
                                size=13,
                                weight=ft.FontWeight.W_500,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(8, 8, 8, 8),
            border_radius=10,
            on_click=lambda e, u=url, t=stored_title: on_play(u, t),
            ink=True,
        )

    if not history:
        empty_controls: list = [
            ft.Icon(ft.Icons.HISTORY, size=48, color=AppColors.grey_dim()),
            ft.Text("No watch history yet", size=14, color=AppColors.grey_dim()),
        ]
        if callable(on_back):
            empty_controls.append(
                ft.FilledButton(
                    content=ft.Text("Browse channels"),
                    on_click=lambda e: on_back(),
                    autofocus=True,
                )
            )
        body = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                controls=empty_controls,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
            ),
        )
    else:
        cards = [c for c in (_make_card(entry) for entry in history) if c is not None]
        body = ft.ListView(
            controls=cards,
            expand=True,
            spacing=4,
            padding=ft.Padding(16, 8, 16, 16),
            build_controls_on_demand=True,
            cache_extent=200,
        )

    from components.banner_ad import build_banner_ad

    rw_banner = build_banner_ad(page)

    controls = []
    if rw_banner:
        controls.append(rw_banner)
    controls.append(body)

    return ft.Column(
        controls=controls,
        expand=True,
        spacing=0,
    )
