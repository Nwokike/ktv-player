"""FilterBar — sticky row of 4 filter chips for the Home screen.

Chips: Country, Category, Favorites-only toggle, Source (All/Built-in/Custom).
Each chip opens a simple dropdown overlay when tapped.

This is a @ft.component because it owns use_state for the open-dropdown
tracking. Tests are at the helper level; full rendering verified in manual
smoke.
"""

from collections.abc import Callable

import flet as ft
from flet.controls.control import Control


@ft.component
def FilterBar(
    filters: dict,
    on_change: Callable[[dict], None],
    available_countries: list[str],
    available_categories: list[str],
    user_country: str,
    total_count: int = 0,
) -> Control:
    """Render filter chips.

    Args:
        filters: current filter state dict.
        on_change: fires with updated dict when a filter item is selected.
        available_countries: sorted list of country names from channel data.
        available_categories: sorted list of category strings.
        user_country: user-preferred country (shown first in country list).
        total_count: number of visible channels after filter.
    """
    open_dropdown, set_open_dropdown = ft.use_state(None)

    def _fire(new_partial: dict):
        updated = {**filters, **new_partial}
        if callable(on_change):
            on_change(updated)
        set_open_dropdown(None)

    def _toggle_fav():
        _fire({"fav_only": not filters.get("fav_only", False)})

    def _chip(label: str, icon, selected: bool, on_click):
        return ft.Chip(
            label=ft.Text(label, size=13),
            leading=ft.Icon(icon, size=16),
            selected=selected,
            on_click=on_click,
        )

    def _dropdown_overlay(items: list[tuple[str, Callable]]) -> Control:
        return ft.Container(
            width=220,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
            border_radius=12,
            padding=6,
            content=ft.Column(
                controls=[
                    ft.Container(
                        content=ft.TextButton(
                            content=ft.Text(label, size=14, weight=ft.FontWeight.W_500),
                            on_click=lambda e, a=action: a(),
                        ),
                        padding=2,
                    )
                    for label, action in items
                ],
                spacing=2,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    intro = ft.Chip(
        label=ft.Text(
            f"{total_count} channels" if total_count else "All channels", size=13
        ),
    )

    country_label = filters["country"] if filters["country"] != "all" else "Country"
    category_label = filters["category"] if filters["category"] != "all" else "Category"
    source_label = {"all": "Source", "built-in": "Built-in", "custom": "Custom"}.get(
        filters["source"], "Source"
    )

    chips = [
        intro,
        _chip(
            country_label,
            ft.Icons.PUBLIC,
            filters["country"] != "all",
            lambda e: set_open_dropdown(
                "country" if open_dropdown != "country" else None
            ),
        ),
        _chip(
            category_label,
            ft.Icons.CATEGORY,
            filters["category"] != "all",
            lambda e: set_open_dropdown(
                "category" if open_dropdown != "category" else None
            ),
        ),
        _chip(
            "★ Fav" if filters["fav_only"] else "Fav",
            ft.Icons.STAR if filters["fav_only"] else ft.Icons.STAR_BORDER,
            filters["fav_only"],
            lambda e: _toggle_fav(),
        ),
        _chip(
            source_label,
            ft.Icons.SOURCE,
            filters["source"] != "all",
            lambda e: set_open_dropdown(
                "source" if open_dropdown != "source" else None
            ),
        ),
    ]

    # Build overlays
    overlays_col = []
    if open_dropdown == "country":
        items = list(available_countries)
        if user_country in items:
            items.remove(user_country)
            items.insert(0, user_country)
        overlays_col.append(
            _dropdown_overlay(
                [("All", lambda: _fire({"country": "all"}))]
                + [(n, lambda n=n: _fire({"country": n})) for n in items],
            )
        )
    elif open_dropdown == "category":
        overlays_col.append(
            _dropdown_overlay(
                [("All", lambda: _fire({"category": "all"}))]
                + [
                    (n, lambda n=n: _fire({"category": n}))
                    for n in available_categories
                ],
            )
        )
    elif open_dropdown == "source":
        overlays_col.append(
            _dropdown_overlay(
                [
                    ("All", lambda: _fire({"source": "all"})),
                    ("Built-in", lambda: _fire({"source": "built-in"})),
                    ("Custom", lambda: _fire({"source": "custom"})),
                ]
            )
        )

    if overlays_col:
        return ft.Container(
            content=ft.Stack(controls=[*chips, *overlays_col]),
            padding=ft.Padding.symmetric(horizontal=4),
        )
    return ft.Container(
        content=ft.Row(controls=chips, scroll=ft.ScrollMode.AUTO, spacing=6),
        padding=ft.Padding.symmetric(horizontal=4),
    )
