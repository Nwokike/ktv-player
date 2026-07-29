"""FilterBar — sticky row of 4 filter chips for the Home screen.

Chips: Category, Country, Custom (all use ft.Dropdown for focusable select),
Favorites (toggle ft.Chip).
"""

from collections.abc import Callable

import flet as ft
from flet import Control

from core.constants import LBL_ADD_CONTENT
from core.tokens import FONT_MD, ICON_SM, SPACING_XS


# Compact chip-like Dropdown styling
_CHIP_DROPDOWN_STYLE = dict(
    border=ft.InputBorder.NONE,
    dense=True,
    filled=True,
    fill_color=ft.Colors.TRANSPARENT,
    content_padding=ft.Padding(6, 2, 6, 2),
    text_size=FONT_MD,
    border_radius=8,
    height=36,
)


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

    # --- 1. Category ---
    current_category = filters.get("category", "all")

    category_options = [
        ft.DropdownOption(key="all", text="All Categories"),
    ]
    if isinstance(available_categories, dict):
        for cat, count in sorted(available_categories.items(), key=lambda x: x[0]):
            category_options.append(
                ft.DropdownOption(key=cat, text=f"{cat} ({count})")
            )
    else:
        for cat in available_categories:
            category_options.append(ft.DropdownOption(key=cat, text=cat))

    category_dd = ft.Dropdown(
        value=current_category,
        options=category_options,
        leading_icon=ft.Icon(ft.Icons.CATEGORY, size=ICON_SM),
        autofocus=True,
        on_select=lambda e: _fire(
            {"category": e.control.value, "country": "all", "custom": "none"}
        ),
        **_CHIP_DROPDOWN_STYLE,
    )

    # --- 2. Country ---
    current_country = filters.get("country", "all")

    country_options = [
        ft.DropdownOption(key="all", text="All Countries"),
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
            country_options.append(
                ft.DropdownOption(
                    key=user_country,
                    text=f"{user_country} ({u_count}) (Local)",
                )
            )
            sorted_countries.remove(user_country)

        for c_name in sorted_countries:
            c_count = country_dict[c_name]
            country_options.append(
                ft.DropdownOption(key=c_name, text=f"{c_name} ({c_count})")
            )
    else:
        sorted_countries = list(available_countries)
        if (
            user_country
            and user_country != "Other"
            and user_country in sorted_countries
        ):
            country_options.append(
                ft.DropdownOption(key=user_country, text=f"{user_country} (Local)")
            )
            sorted_countries.remove(user_country)

        for c_name in sorted_countries:
            country_options.append(ft.DropdownOption(key=c_name, text=c_name))

    country_dd = ft.Dropdown(
        value=current_country,
        options=country_options,
        leading_icon=ft.Icon(ft.Icons.PUBLIC, size=ICON_SM),
        autofocus=True,
        on_select=lambda e: _fire(
            {"country": e.control.value, "category": "all", "custom": "none"}
        ),
        **_CHIP_DROPDOWN_STYLE,
    )

    # --- 3. Custom ---
    current_custom = filters.get("custom", "none")

    custom_options = [
        ft.DropdownOption(key="single", text="Single Channels"),
    ]
    if custom_playlists:
        for pl in custom_playlists:
            custom_options.append(ft.DropdownOption(key=pl, text=pl))

    # "Add Custom Content" as the last option
    if callable(on_add_content):
        custom_options.append(
            ft.DropdownOption(key="__add__", text=LBL_ADD_CONTENT)
        )

    def _on_custom_select(e):
        val = e.control.value
        if val == "__add__":
            on_add_content()
            return
        _fire({"custom": val, "country": "all", "category": "all"})

    custom_dd = ft.Dropdown(
        value=current_custom,
        options=custom_options,
        leading_icon=ft.Icon(ft.Icons.FOLDER_SPECIAL, size=ICON_SM),
        autofocus=True,
        on_select=_on_custom_select,
        **_CHIP_DROPDOWN_STYLE,
    )

    # --- 4. Favorites Chip (toggle, no dropdown) ---
    fav_selected = filters.get("fav_only", False)
    fav_chip = ft.Chip(
        label=ft.Text("Fav", size=FONT_MD),
        leading=ft.Icon(
            ft.Icons.STAR if fav_selected else ft.Icons.STAR_BORDER, size=ICON_SM
        ),
        selected=fav_selected,
        autofocus=True,
        on_click=lambda e: _toggle_fav(),
    )

    controls_row = [country_dd, category_dd, custom_dd, fav_chip]

    chips_row = ft.Row(
        controls=controls_row,
        scroll=ft.ScrollMode.AUTO,
        spacing=SPACING_XS,
    )

    return ft.Container(
        content=chips_row,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
    )