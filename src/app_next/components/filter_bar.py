"""FilterBar — sticky row of 5 chips for the Home/Local screens.

All four content chips (Country/Category/Custom/Fav) share the same
`_chip_content` shell so the row reads as a uniform strip:
    Country | Category | Custom | Fav | +

The 5th "+" is an `ft.IconButton` action.

Each chip is a single-key writer via `_fire({key: value})`. The four
content chips reset each other (Country/Category/Custom are mutually
exclusive; clicking one fires a partial that nulls the other two — same
behaviour the OLD chip layout had). Fav is its own orthogonal toggle.

Country / Category / Custom open a `ft.SubmenuButton` menu. The venv
verified .venv/lib/python3.14/site-packages/flet/controls/material/
submenu_button.py:50-58: "controls typically either MenuItemButton or
SubmenuButton". We use MenuItemButton — not PopupMenuItem, which is
for PopupMenuButton and triggers "Unknown control" Flutter warnings.

Fav is a flat toggle using `ft.OutlinedButton` so it accepts the same
_button_style + content shape but has no menu.
"""

from collections.abc import Callable

import flet as ft
from flet import Control

from core.constants import LBL_ADD_CONTENT_SHORT
from core.tokens import FONT_MD, ICON_SM, SPACING_XS

# Single visual style applied to every chip shell button.
_CHIP_BTN_STYLE = ft.ButtonStyle(
    bgcolor=ft.Colors.TRANSPARENT,
    elevation=0,
    shadow_color=ft.Colors.TRANSPARENT,
    overlay_color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
    padding=ft.Padding(0, 0, 0, 0),
    shape=ft.RoundedRectangleBorder(radius=8),
)

# Style applied to every dropdown menu (Country/Category/Custom).
_CHIP_MENU_STYLE = ft.MenuStyle(
    bgcolor=ft.Colors.SURFACE,
    shadow_color=ft.Colors.with_opacity(0.15, ft.Colors.BLACK),
    elevation=4,
    padding=ft.Padding(0, 4, 0, 4),
    shape=ft.RoundedRectangleBorder(radius=8),
)


def _chip_content(
    label: str,
    icon: str,
    is_selected: bool,
) -> ft.Control:
    """Common visual body for every chip. Returns the visible content of
    the chip shell (icon | text | arrow). All 5 chips use this exact
    shape so the row reads uniformly.
    """
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(icon, size=ICON_SM),
                ft.Text(label, size=FONT_MD),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=ICON_SM),
            ],
            spacing=2,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(8, 4, 8, 4),
        border=ft.Border.all(
            1,
            ft.Colors.with_opacity(
                0.3,
                ft.Colors.OUTLINE_VARIANT if not is_selected else ft.Colors.PRIMARY,
            ),
        ),
        border_radius=8,
        bgcolor=ft.Colors.with_opacity(
            0.08, ft.Colors.PRIMARY if is_selected else ft.Colors.TRANSPARENT
        ),
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
    """Render 5 chips: Country / Category / Custom / Fav / +.

    All four content chips share the `_chip_content` shell. Country,
    Category, Custom reset each other when picked (radio behaviour
    preserved from the legacy filter_bar). Fav stacks independently.
    The "+" chip lives in the same Row but is a separate action.

    Contract preserved: writes the 4-key filter dict
        {country, category, custom, fav_only}
    via `_fire({...})`. callers don't change.
    """

    def _fire(partial: dict):
        if callable(on_change):
            on_change(partial)

    # ---- 1. Country ----
    current_country = filters.get("country", "all")
    country_label = current_country if current_country != "all" else "Country"
    country_active = current_country != "all"
    country_menu_items: list[Control] = [
        ft.MenuItemButton(
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
                ft.MenuItemButton(
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
                ft.MenuItemButton(
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
                ft.MenuItemButton(
                    content=ft.Text(f"{user_country} (Local)", size=FONT_MD),
                    on_click=lambda e, u=user_country: _fire(
                        {"country": u, "category": "all", "custom": "none"}
                    ),
                )
            )
            sorted_countries.remove(user_country)
        country_menu_items.extend(
            [
                ft.MenuItemButton(
                    content=ft.Text(c_name, size=FONT_MD),
                    on_click=lambda e, c=c_name: _fire(
                        {"country": c, "category": "all", "custom": "none"}
                    ),
                )
                for c_name in sorted_countries
            ]
        )
    country_btn = ft.SubmenuButton(
        content=_chip_content(
            country_label, ft.Icons.PUBLIC, country_active
        ),
        controls=country_menu_items,
        style=_CHIP_BTN_STYLE,
        menu_style=_CHIP_MENU_STYLE,
    )

    # ---- 2. Category ----
    current_category = filters.get("category", "all")
    category_label = (
        current_category if current_category != "all" else "Category"
    )
    category_active = current_category != "all"
    category_items: list[Control] = [
        ft.MenuItemButton(
            content=ft.Text("All Categories", size=FONT_MD),
            on_click=lambda e: _fire(
                {"category": "all", "country": "all", "custom": "none"}
            ),
        )
    ]
    if isinstance(available_categories, dict):
        for cat, count in sorted(
            available_categories.items(), key=lambda x: x[0]
        ):
            category_items.append(
                ft.MenuItemButton(
                    content=ft.Text(f"{cat} ({count})", size=FONT_MD),
                    on_click=lambda e, c=cat: _fire(
                        {"category": c, "country": "all", "custom": "none"}
                    ),
                )
            )
    else:
        for cat in available_categories:
            category_items.append(
                ft.MenuItemButton(
                    content=ft.Text(cat, size=FONT_MD),
                    on_click=lambda e, c=cat: _fire(
                        {"category": c, "country": "all", "custom": "none"}
                    ),
                )
            )
    category_btn = ft.SubmenuButton(
        content=_chip_content(
            category_label, ft.Icons.CATEGORY, category_active
        ),
        controls=category_items,
        style=_CHIP_BTN_STYLE,
        menu_style=_CHIP_MENU_STYLE,
    )

    # ---- 3. Custom ----
    current_custom = filters.get("custom", "none")
    custom_active = current_custom != "none"
    custom_label = (
        "Custom"
        if current_custom == "none"
        else ("Single Channels" if current_custom == "single" else current_custom)
    )
    custom_menu_items: list[Control] = [
        ft.MenuItemButton(
            content=ft.Text("Single Channels", size=FONT_MD),
            on_click=lambda e: _fire(
                {"custom": "single", "country": "all", "category": "all"}
            ),
        )
    ]
    if custom_playlists:
        for pl in custom_playlists:
            custom_menu_items.append(
                ft.MenuItemButton(
                    content=ft.Text(pl, size=FONT_MD),
                    on_click=lambda e, name=pl: _fire(
                        {"custom": name, "country": "all", "category": "all"}
                    ),
                )
            )
    custom_btn = ft.SubmenuButton(
        content=_chip_content(
            custom_label, ft.Icons.FOLDER_SPECIAL, custom_active
        ),
        controls=custom_menu_items,
        style=_CHIP_BTN_STYLE,
        menu_style=_CHIP_MENU_STYLE,
    )

    # ---- 4. Fav (OutlinedButton, no menu) ----
    fav_selected = filters.get("fav_only", False)

    def _toggle_fav():
        _fire({"fav_only": not fav_selected})

    fav_btn = ft.OutlinedButton(
        content=_chip_content("Fav", ft.Icons.STAR, fav_selected),
        style=_CHIP_BTN_STYLE,
        on_click=lambda e: _toggle_fav(),
    )

    # ---- 5. + (IconButton, no menu) ----
    controls_row: list[Control] = [
        country_btn,
        category_btn,
        custom_btn,
        fav_btn,
    ]
    if callable(on_add_content):
        controls_row.append(
            ft.IconButton(
                icon=ft.Icons.ADD,
                tooltip=LBL_ADD_CONTENT_SHORT,
                on_click=lambda e: on_add_content(),
                icon_size=ICON_SM,
                style=ft.ButtonStyle(padding=ft.Padding(8, 4, 8, 4)),
            )
        )

    return ft.Container(
        content=ft.Row(
            controls=controls_row,
            scroll=ft.ScrollMode.AUTO,
            spacing=SPACING_XS,
        ),
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
    )
