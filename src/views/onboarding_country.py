"""Country list tile builder for onboarding view."""

import flet as ft

from core.theme import AppColors


def build_country_list(
    current_countries: list[dict], selected_state: dict, page_obj: ft.Page
) -> ft.Container:
    """Build country selection list view container."""
    country_list = ft.ListView(height=180, spacing=2, padding=5, auto_scroll=False)
    country_tiles = []

    def select_country(cname):
        selected_state["country"] = cname
        for entry in country_tiles:
            is_sel = entry["name"] == cname
            entry["tile"].bgcolor = AppColors.PRIMARY if is_sel else None
            entry["tile"].leading = ft.Icon(
                ft.Icons.CHECK_CIRCLE if is_sel else ft.Icons.RADIO_BUTTON_UNCHECKED,
                color=ft.Colors.WHITE if is_sel else AppColors.GREY_DIM,
            )
            entry["tile"].title = ft.Text(
                entry["name"],
                color=ft.Colors.WHITE if is_sel else None,
                weight=ft.FontWeight.W_600 if is_sel else ft.FontWeight.NORMAL,
            )
        country_list.update()

    for c in current_countries:
        cname = c.get("name", "")
        tile = ft.ListTile(
            title=ft.Text(cname),
            leading=ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, color=AppColors.GREY_DIM),
            key=cname,
            on_click=lambda e, n=cname: select_country(n),
            dense=True,
            shape=ft.RoundedRectangleBorder(radius=8),
        )
        country_tiles.append({"name": cname, "tile": tile})
        country_list.controls.append(tile)

    return ft.Container(
        content=country_list,
        border=ft.Border.all(1, AppColors.get_border_color(page_obj)),
        border_radius=12,
        padding=4,
    )
