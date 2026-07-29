"""FilterBar — sticky row of 4 filter chips for the Home screen.

Chips: Category (Dropdown), Country (Dropdown), Custom (Dropdown), Favorites (Toggle).
Uses Flet PopupMenuButton for Material 3 dropdown menus.
"""

from collections.abc import Callable

import flet as ft
from flet.controls.control import Control

from core.tokens import FONT_MD, ICON_SM, SPACING_XS


@ft.component
def FilterBar(
    filters: dict,
    on_change: Callable[[dict], None],
    available_countries: list[str] | dict[str, int],
    available_categories: list[str] | dict[str, int],
    user_country: str,
    custom_playlists: list[str] | None = None,
    total_count: int = 0,
    on_add_content: Callable[[], None] | None = None,
) -> Control:
    """Render filter chips.

    Args:
        filters: current filter state dict.
        on_change: fires with updated dict when a filter item is selected.
        available_countries: sorted list of country names or dict mapping name to count.
        available_categories: sorted list of category strings or dict mapping name to count.
        user_country: user-preferred country (pinned near top of country list).
        custom_playlists: list of user-added playlist names.
        total_count: number of visible channels after filter.
        on_add_content: optional callback to add custom content.
    """

    def _fire(new_partial: dict):
        updated = {**filters, **new_partial}
        if callable(on_change):
            on_change(updated)

    def _toggle_fav():
        _fire({"fav_only": not filters.get("fav_only", False)})

    # --- 1. Category Chip & Menu ---
    current_category = filters.get("category", "all")
    category_label = current_category if current_category != "all" else "Category"
    category_items = [
        ft.PopupMenuItem(
            content=ft.Text("All Categories", size=FONT_MD),
            on_click=lambda e: _fire(
                {"category": "all", "country": "all", "custom": "none"}
            ),
        )
    ]
    if isinstance(available_categories, dict):
        for cat, count in sorted(available_categories.items(), key=lambda x: x[0]):
            category_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(f"{cat} ({count})", size=FONT_MD),
                    on_click=lambda e, c=cat: _fire(
                        {"category": c, "country": "all", "custom": "none"}
                    ),
                )
            )
    else:
        for cat in available_categories:
            category_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(cat, size=FONT_MD),
                    on_click=lambda e, c=cat: _fire(
                        {"category": c, "country": "all", "custom": "none"}
                    ),
                )
            )

    category_btn = ft.PopupMenuButton(
        content=ft.Chip(
            label=ft.Row(
                controls=[
                    ft.Text(category_label, size=FONT_MD),
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=ICON_SM),
                ],
                spacing=2,
                tight=True,
            ),
            leading=ft.Icon(ft.Icons.CATEGORY, size=ICON_SM),
            selected=current_category != "all",
        ),
        items=category_items,
        menu_position=ft.PopupMenuPosition.UNDER,
    )

    # --- 2. Country Chip & Menu ---
    current_country = filters.get("country", "all")
    country_label = current_country if current_country != "all" else "Country"

    country_menu_items = [
        ft.PopupMenuItem(
            content=ft.Text("All Countries", size=FONT_MD),
            on_click=lambda e: _fire(
                {"country": "all", "category": "all", "custom": "none"}
            ),
        )
    ]

    if isinstance(available_countries, dict):
        country_dict = available_countries
        sorted_countries = sorted(country_dict.keys())
        if (
            user_country
            and user_country != "Other"
            and user_country in sorted_countries
        ):
            u_count = country_dict[user_country]
            country_menu_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(
                        f"{user_country} ({u_count}) (Local)", size=FONT_MD
                    ),
                    on_click=lambda e, u=user_country: _fire(
                        {"country": u, "category": "all", "custom": "none"}
                    ),
                )
            )
            sorted_countries.remove(user_country)

        for c_name in sorted_countries:
            c_count = country_dict[c_name]
            country_menu_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(f"{c_name} ({c_count})", size=FONT_MD),
                    on_click=lambda e, c=c_name: _fire(
                        {"country": c, "category": "all", "custom": "none"}
                    ),
                )
            )
    else:
        sorted_countries = list(available_countries)
        if (
            user_country
            and user_country != "Other"
            and user_country in sorted_countries
        ):
            country_menu_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(f"{user_country} (Local)", size=FONT_MD),
                    on_click=lambda e, u=user_country: _fire(
                        {"country": u, "category": "all", "custom": "none"}
                    ),
                )
            )
            sorted_countries.remove(user_country)

        country_menu_items.extend(
            [
                ft.PopupMenuItem(
                    content=ft.Text(c_name, size=FONT_MD),
                    on_click=lambda e, c=c_name: _fire(
                        {"country": c, "category": "all", "custom": "none"}
                    ),
                )
                for c_name in sorted_countries
            ]
        )

    country_btn = ft.PopupMenuButton(
        content=ft.Chip(
            label=ft.Row(
                controls=[
                    ft.Text(country_label, size=FONT_MD),
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=ICON_SM),
                ],
                spacing=2,
                tight=True,
            ),
            leading=ft.Icon(ft.Icons.PUBLIC, size=ICON_SM),
            selected=current_country != "all",
        ),
        items=country_menu_items,
        menu_position=ft.PopupMenuPosition.UNDER,
    )

    # --- 3. Custom Chip & Menu ---
    current_custom = filters.get("custom", "none")
    custom_label = (
        "Custom"
        if current_custom == "none"
        else ("Single Channels" if current_custom == "single" else current_custom)
    )

    custom_menu_items = [
        ft.PopupMenuItem(
            content=ft.Text("Single Channels", size=FONT_MD),
            on_click=lambda e: _fire(
                {"custom": "single", "country": "all", "category": "all"}
            ),
        ),
    ]
    if custom_playlists:
        for pl in custom_playlists:
            custom_menu_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(pl, size=FONT_MD),
                    on_click=lambda e, name=pl: _fire(
                        {"custom": name, "country": "all", "category": "all"}
                    ),
                )
            )

    custom_btn = ft.PopupMenuButton(
        content=ft.Chip(
            label=ft.Row(
                controls=[
                    ft.Text(custom_label, size=FONT_MD),
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=ICON_SM),
                ],
                spacing=2,
                tight=True,
            ),
            leading=ft.Icon(ft.Icons.FOLDER_SPECIAL, size=ICON_SM),
            selected=current_custom != "none",
        ),
        items=custom_menu_items,
        menu_position=ft.PopupMenuPosition.UNDER,
    )

    # --- 4. Favorites Chip ---
    fav_selected = filters.get("fav_only", False)
    fav_chip = ft.Chip(
        label=ft.Text("★ Fav" if fav_selected else "Fav", size=FONT_MD),
        leading=ft.Icon(
            ft.Icons.STAR if fav_selected else ft.Icons.STAR_BORDER, size=ICON_SM
        ),
        selected=fav_selected,
        on_click=lambda e: _toggle_fav(),
    )

    controls_row = [country_btn, category_btn, custom_btn, fav_chip]

    if callable(on_add_content):
        add_btn = ft.IconButton(
            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
            icon_size=ICON_SM + 4,
            tooltip="Add Custom Content",
            on_click=lambda e: on_add_content(),
        )
        controls_row.append(add_btn)

    chips_row = ft.Row(
        controls=controls_row,
        scroll=ft.ScrollMode.AUTO,
        spacing=SPACING_XS,
    )

    return ft.Container(
        content=chips_row,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
    )
