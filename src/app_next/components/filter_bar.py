"""FilterBar — sticky row of filter chips for the Home/Local screens.

Country / Category / Custom are PopupMenuButton triggers that render as
compact outlined pills (icon + label + chevron). Clicking opens a popup
menu. Fav is an OutlinedButton toggle. The + is an IconButton.
"""

from collections.abc import Callable

import flet as ft
from flet import Control

from core.constants import LBL_ADD_CONTENT_SHORT
from core.tokens import FONT_MD, ICON_SM, SPACING_XS

# Transparent wrapper so PopupMenuButton adds no visible chrome
_TRIGGER_STYLE = ft.ButtonStyle(
    bgcolor=ft.Colors.TRANSPARENT,
    elevation=0,
    shadow_color=ft.Colors.TRANSPARENT,
    overlay_color=ft.Colors.with_opacity(0.06, ft.Colors.WHITE),
    padding=ft.Padding(0, 0, 0, 0),
    shape=ft.RoundedRectangleBorder(radius=8),
)

# Menu dropdown styling — PopupMenuButton uses direct params, not MenuStyle
_MENU_BG = ft.Colors.SURFACE
_MENU_SHADOW = ft.Colors.with_opacity(0.15, ft.Colors.BLACK)
_MENU_ELEVATION = 4
_MENU_PADDING = ft.Padding(0, 4, 0, 4)
_MENU_SHAPE = ft.RoundedRectangleBorder(radius=8)

def _pill(label: str, icon: str, is_selected: bool, show_arrow: bool = True) -> ft.Control:
    """Compact outlined pill: icon + text + chevron."""
    border_color = (
        ft.Colors.PRIMARY
        if is_selected
        else ft.Colors.with_opacity(0.3, ft.Colors.OUTLINE_VARIANT)
    )
    bg = (
        ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY)
        if is_selected
        else ft.Colors.TRANSPARENT
    )
    controls = [
        ft.Icon(icon, size=ICON_SM),
        ft.Text(label, size=FONT_MD, no_wrap=True),
    ]
    if show_arrow:
        controls.append(ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=ICON_SM))

    return ft.Container(
        content=ft.Row(
            controls=controls,
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(8, 4, 8, 4),
        border=ft.Border.all(1, border_color),
        border_radius=8,
        bgcolor=bg,
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
    """Render filter pills: Country / Category / Custom / Fav / +."""

    def _fire(partial: dict):
        if callable(on_change):
            on_change(partial)

    # ---- 1. Country ----
    current_country = filters.get("country", "all")
    country_label = current_country if current_country != "all" else "Country"

    is_dict = isinstance(available_countries, dict)
    sorted_countries = sorted(available_countries.keys() if is_dict else available_countries)

    def _country_label(name: str) -> str:
        if is_dict:
            return f"{name} ({available_countries[name]})"
        return name

    _RESET = {"fav_only": False, "search": ""}

    country_items: list[ft.PopupMenuItem] = [
        ft.PopupMenuItem(
            content=ft.Text("All Countries", size=FONT_MD),
            on_click=lambda e: _fire(
                {"country": "all", "category": "all", "custom": "none", **_RESET}
            ),
        ),
    ]
    if user_country and user_country != "Other" and user_country in sorted_countries:
        suffix = " (Local)" if not is_dict else f" ({available_countries[user_country]}) (Local)"
        country_items.append(
            ft.PopupMenuItem(
                content=ft.Text(f"{user_country}{suffix}", size=FONT_MD),
                on_click=lambda e, u=user_country: _fire(
                    {"country": u, "category": "all", "custom": "none", **_RESET}
                ),
            )
        )
        sorted_countries.remove(user_country)
    for c_name in sorted_countries:
        country_items.append(
            ft.PopupMenuItem(
                content=ft.Text(_country_label(c_name), size=FONT_MD),
                on_click=lambda e, c=c_name: _fire(
                    {"country": c, "category": "all", "custom": "none", **_RESET}
                ),
            )
        )

    country_items.insert(
        0,
        ft.PopupMenuItem(
            content=ft.Text("Cancel", size=FONT_MD),
            on_click=lambda e: _fire({"country": "all", "category": "all", "custom": "none", **_RESET}),
        ),
    )

    country_btn = ft.PopupMenuButton(
        content=_pill(country_label, ft.Icons.PUBLIC, current_country != "all"),
        items=country_items,
        menu_position=ft.PopupMenuPosition.UNDER,
        style=_TRIGGER_STYLE,
        bgcolor=_MENU_BG,
        shadow_color=_MENU_SHADOW,
        elevation=_MENU_ELEVATION,
        menu_padding=_MENU_PADDING,
        shape=_MENU_SHAPE,
    )

    # ---- 2. Category ----
    current_category = filters.get("category", "all")
    category_label = current_category if current_category != "all" else "Category"

    category_items: list[ft.PopupMenuItem] = [
        ft.PopupMenuItem(
            content=ft.Text("All Categories", size=FONT_MD),
            on_click=lambda e: _fire(
                {"category": "all", "country": "all", "custom": "none", **_RESET}
            ),
        ),
    ]
    if isinstance(available_categories, dict):
        for cat, count in sorted(available_categories.items(), key=lambda x: x[0]):
            category_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(f"{cat} ({count})", size=FONT_MD),
                    on_click=lambda e, c=cat: _fire(
                        {"category": c, "country": "all", "custom": "none", **_RESET}
                    ),
                )
            )
    else:
        for cat in available_categories:
            category_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(cat, size=FONT_MD),
                    on_click=lambda e, c=cat: _fire(
                        {"category": c, "country": "all", "custom": "none", **_RESET}
                    ),
                )
            )

    category_items.insert(
        0,
        ft.PopupMenuItem(
            content=ft.Text("Cancel", size=FONT_MD),
            on_click=lambda e: _fire({"category": "all", "country": "all", "custom": "none", **_RESET}),
        ),
    )

    category_btn = ft.PopupMenuButton(
        content=_pill(category_label, ft.Icons.CATEGORY, current_category != "all"),
        items=category_items,
        menu_position=ft.PopupMenuPosition.UNDER,
        style=_TRIGGER_STYLE,
        bgcolor=_MENU_BG,
        shadow_color=_MENU_SHADOW,
        elevation=_MENU_ELEVATION,
        menu_padding=_MENU_PADDING,
        shape=_MENU_SHAPE,
    )

    # ---- 3. Custom ----
    current_custom = filters.get("custom", "none")
    custom_label = (
        "Custom"
        if current_custom == "none"
        else ("Single Channels" if current_custom == "single" else current_custom)
    )

    custom_items: list[ft.PopupMenuItem] = [
        ft.PopupMenuItem(
            content=ft.Text("Single Channels", size=FONT_MD),
            on_click=lambda e: _fire(
                {"custom": "single", "country": "all", "category": "all", **_RESET}
            ),
        ),
    ]
    if custom_playlists:
        for pl in custom_playlists:
            custom_items.append(
                ft.PopupMenuItem(
                    content=ft.Text(pl, size=FONT_MD),
                    on_click=lambda e, name=pl: _fire(
                        {"custom": name, "country": "all", "category": "all", **_RESET}
                    ),
                )
            )
    if callable(on_add_content):
        custom_items.append(
            ft.PopupMenuItem(
                content=ft.Text(LBL_ADD_CONTENT_SHORT, size=FONT_MD),
                on_click=lambda e: on_add_content(),
            )
            )

    custom_items.insert(
        0,
        ft.PopupMenuItem(
            content=ft.Text("Cancel", size=FONT_MD),
            on_click=lambda e: _fire({"custom": "none", "country": "all", "category": "all", **_RESET}),
        ),
    )

    custom_btn = ft.PopupMenuButton(
        content=_pill(custom_label, ft.Icons.FOLDER_SPECIAL, current_custom != "none"),
        items=custom_items,
        menu_position=ft.PopupMenuPosition.UNDER,
        style=_TRIGGER_STYLE,
        bgcolor=_MENU_BG,
        shadow_color=_MENU_SHADOW,
        elevation=_MENU_ELEVATION,
        menu_padding=_MENU_PADDING,
        shape=_MENU_SHAPE,
    )

    # ---- 4. Fav (single-click toggle, no dropdown — same pill style) ----
    fav_selected = filters.get("fav_only", False)
    fav_label = "Fav"
    fav_border = ft.Colors.PRIMARY if fav_selected else ft.Colors.with_opacity(0.3, ft.Colors.OUTLINE_VARIANT)
    fav_bg = ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY) if fav_selected else ft.Colors.TRANSPARENT

    fav_btn = ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.STAR if fav_selected else ft.Icons.STAR_BORDER, size=ICON_SM),
                ft.Text(fav_label, size=FONT_MD, no_wrap=True),
            ],
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding(8, 4, 8, 4),
        border=ft.Border.all(1, fav_border),
        border_radius=8,
        bgcolor=fav_bg,
        on_click=lambda e: _fire({"fav_only": not fav_selected, "country": "all", "category": "all", "custom": "none", "search": ""}),
        ink=True,
    )

    # ---- 5. + (add) — same PopupMenuButton style ----
    controls_row: list[Control] = [
        country_btn,
        category_btn,
        custom_btn,
        fav_btn,
    ]
    if callable(on_add_content):
        controls_row.append(
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Text("+", size=FONT_MD, no_wrap=True),
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=ft.Padding(8, 4, 8, 4),
                border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.OUTLINE_VARIANT)),
                border_radius=8,
                on_click=lambda e: on_add_content(),
                ink=True,
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
