"""FilterBar — sticky row of 5 chips for the Home/Local screens.

The four content chips (Country / Category / Custom / Fav) read as a
uniform strip:
    Country | Category | Custom | Fav | +

Country / Category / Custom are click-to-open dropdowns: at rest they
show the leading icon + a tiny chevron; clicking (or pressing Enter
when focused via D-pad) reveals the option list. This matches the
D-pad-natural flow the user asked for. Verified
.venv/lib/python3.14/site-packages/flet/controls/material/dropdown.py:60-115:
value, options=[DropdownOption(...)], leading_icon, on_select,
on_focus/on_blur.

Fav is a flat toggle (OutlinedButton) so it accepts the same
`ButtonStyle` + content shape but has no menu.

The 5th "+" is an IconButton action.

Each chip is a single-key writer via `_fire({key: value})`. Country /
Category / Custom reset each other when picked (radio behaviour).
Fav stacks independently.
"""

from collections.abc import Callable

import flet as ft
from flet import Control

from core.constants import LBL_ADD_CONTENT_SHORT
from core.tokens import FONT_MD, ICON_SM, SPACING_XS

# Style applied to every chip's click-to-open dropdown trigger.
# Verified .venv/.../material/dropdown.py:198-260: dropdown accepts
# border, dense, filled, fill_color, content_padding, text_size,
# border_radius, height. The pattern below renders a compact
# outlined field with leading_icon at the front and a chevron at the
# back - no menu is shown until the user clicks/focuses+enters.
_CHIP_DROPDOWN_STYLE = dict(  # noqa: C408
    border=ft.InputBorder.NONE,
    dense=True,
    filled=True,
    fill_color=ft.Colors.TRANSPARENT,
    content_padding=ft.Padding(6, 2, 6, 2),
    text_size=FONT_MD,
    border_radius=8,
    height=36,
)

# Style applied to Fav (no menu). Matches the dropdown chrome so the
# four chips look uniform.
_CHIP_BTN_STYLE = ft.ButtonStyle(
    bgcolor=ft.Colors.TRANSPARENT,
    elevation=0,
    shadow_color=ft.Colors.TRANSPARENT,
    overlay_color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
    padding=ft.Padding(0, 0, 0, 0),
    shape=ft.RoundedRectangleBorder(radius=8),
)


def _chip_content(
    label: str,
    icon: str,
    is_selected: bool,
) -> ft.Control:
    """Common visual body for the Fav chip (OutlinedButton.content).

    Not used by Country/Category/Custom Dropdown chips, which use
    their own leading_icon + native chevron and render as a compact
    outlined field at rest.
    """
    return ft.Container(
        content=ft.Row(
            controls=[
                ft.Icon(icon, size=ICON_SM),
                ft.Text(label, size=FONT_MD),
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

    The first three are click-to-open Dropdowns (verified
    .venv/.../material/dropdown.py:60-115). At rest they show only
    their leading icon + chevron, hiding the label until you click.
    Click (or focus+enter via D-pad) reveals the option list.

    Fav is a flat toggle (OutlinedButton) and "+" is an IconButton.

    Contract preserved: writes the 4-key filter dict
        {country, category, custom, fav_only}
    via `_fire({...})`. callers don't change.
    """

    def _fire(partial: dict):
        if callable(on_change):
            on_change(partial)

    def _on_dropdown_pick(key: str, value: str, partial: dict):
        """Dropdown on_select handler. The Dropdown emits when the user
        picks an option; we just _fire the partial."""
        del key, value  # value is implicit in the closure's partial
        _fire(partial)

    # ---- 1. Country ----
    current_country = filters.get("country", "all")
    country_options: list[ft.DropdownOption] = [
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
            country_options.append(
                ft.DropdownOption(key=c_name, text=c_name)
            )

    def _on_country_pick(e):
        val = e.control.value
        if val is None or val == "all":
            _fire({"country": "all", "category": "all", "custom": "none"})
        else:
            _fire(
                {"country": val, "category": "all", "custom": "none"}
            )

    country_btn = ft.Dropdown(
        value=current_country,
        options=country_options,
        leading_icon=ft.Icon(ft.Icons.PUBLIC, size=ICON_SM),
        hint_text="Country" if current_country == "all" else None,
        on_select=_on_country_pick,
        **_CHIP_DROPDOWN_STYLE,
    )

    # ---- 2. Category ----
    current_category = filters.get("category", "all")
    category_options: list[ft.DropdownOption] = [
        ft.DropdownOption(key="all", text="All Categories"),
    ]
    if isinstance(available_categories, dict):
        for cat, count in sorted(
            available_categories.items(), key=lambda x: x[0]
        ):
            category_options.append(
                ft.DropdownOption(key=cat, text=f"{cat} ({count})")
            )
    else:
        for cat in available_categories:
            category_options.append(
                ft.DropdownOption(key=cat, text=cat)
            )

    def _on_category_pick(e):
        val = e.control.value
        if val is None or val == "all":
            _fire({"category": "all", "country": "all", "custom": "none"})
        else:
            _fire(
                {"category": val, "country": "all", "custom": "none"}
            )

    category_btn = ft.Dropdown(
        value=current_category,
        options=category_options,
        leading_icon=ft.Icon(ft.Icons.CATEGORY, size=ICON_SM),
        hint_text="Category" if current_category == "all" else None,
        on_select=_on_category_pick,
        **_CHIP_DROPDOWN_STYLE,
    )

    # ---- 3. Custom ----
    current_custom = filters.get("custom", "none")
    custom_options: list[ft.DropdownOption] = [
        ft.DropdownOption(key="single", text="Single Channels"),
    ]
    if custom_playlists:
        for pl in custom_playlists:
            custom_options.append(ft.DropdownOption(key=pl, text=pl))

    def _on_custom_pick(e):
        val = e.control.value
        if val is None:
            return
        _fire({"custom": val, "country": "all", "category": "all"})

    # `value` must be a real option key or None. Map "none" -> None so
    # the dropdown displays the hint_text instead of an invalid key.
    custom_value = None if current_custom == "none" else current_custom
    custom_btn = ft.Dropdown(
        value=custom_value,
        options=custom_options,
        leading_icon=ft.Icon(ft.Icons.FOLDER_SPECIAL, size=ICON_SM),
        hint_text="Custom" if current_custom == "none" else None,
        on_select=_on_custom_pick,
        **_CHIP_DROPDOWN_STYLE,
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
