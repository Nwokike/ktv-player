import contextlib

import flet as ft

from components.ui.glass_container import GlassContainer
from core.theme import AppColors
from database.manager import db_manager
from services.liveliness import liveliness_cache
from services.logo_cache import get_cached_logo, download_logo


def create_channel_card(c, card_index=0, on_play=None, page_obj=None, on_fav_change=None):
    url = c.get("url", "")
    cached = liveliness_cache.get(url)
    initial_color = AppColors.GREY_DIM
    if cached is True:
        initial_color = AppColors.SUCCESS
    elif cached is False:
        initial_color = AppColors.ERROR

    status_indicator = ft.Container(
        width=10, height=10, border_radius=5, bgcolor=initial_color
    )

    fav_state = {"is_fav": False}
    fav_icon = ft.Icon(ft.Icons.FAVORITE_BORDER, size=16, color=ft.Colors.WHITE_70)

    card_key = f"ch_{card_index}_{hash(url) % 10000}"
    logo_src = c.get("logo", "/icon.png")

    if logo_src.startswith("/"):
        initial_src = logo_src
    else:
        disk_cached = get_cached_logo(logo_src)
        if disk_cached:
            initial_src = disk_cached
        else:
            initial_src = logo_src
            if page_obj:
                page_obj.run_task(download_logo, logo_src)

    logo_img = ft.Image(
        src=initial_src,
        width=60,
        height=60,
        fit=ft.BoxFit.CONTAIN,
        border_radius=20,
        error_content=ft.Icon(ft.Icons.TV, size=30),
    )

    card_visual = GlassContainer(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=fav_icon,
                            on_click=lambda e, u=url, n=c.get("name", ""), logo=logo_src: _toggle_fav(
                                e, u, n, logo, fav_state, fav_icon, on_fav_change, page_obj,
                            ),
                            tooltip="Add to favorites",
                        ),
                        status_indicator,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                logo_img,
                ft.Text(
                    c.get("name", "Unknown"),
                    size=11,
                    weight=ft.FontWeight.W_400,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=2,
        ),
        padding=10,
        border_radius=25,
        focusable=True,
        key=card_key,
    )

    interactive_card = ft.Container(
        content=card_visual,
        border_radius=25,
        ink=True,
        height=130,
        on_click=lambda e, play_url=url: page_obj.run_task(on_play, play_url) if on_play else None,
    )

    interactive_card.data = {"url": url, "indicator": status_indicator}
    return interactive_card


def _toggle_fav(e, url, name, logo, fav_state, fav_icon, on_fav_change, page_obj):
    async def _do():
        try:
            if fav_state["is_fav"]:
                await db_manager.remove_favorite(url)
                fav_state["is_fav"] = False
                fav_icon.name = ft.Icons.FAVORITE_BORDER
                fav_icon.color = ft.Colors.WHITE_70
            else:
                await db_manager.add_favorite(url, name, logo)
                fav_state["is_fav"] = True
                fav_icon.name = ft.Icons.FAVORITE
                fav_icon.color = AppColors.PRIMARY
            if on_fav_change:
                on_fav_change()
        except Exception:
            pass
    page_obj.run_task(_do)


def build_channel_grid(channels, offset=0, limit=24, on_play=None, page_obj=None, ad_service=None, on_fav_change=None):
    page_channels = channels[offset : offset + limit]
    grid = ft.ResponsiveRow(spacing=12, run_spacing=12)

    for i, c in enumerate(page_channels):
        global_idx = offset + i
        card = create_channel_card(
            c, card_index=global_idx, on_play=on_play, page_obj=page_obj,
            on_fav_change=on_fav_change,
        )
        card_wrapper = ft.Container(
            content=card,
            col={"xs": 4, "sm": 3, "md": 2, "lg": 2},
        )
        grid.controls.append(card_wrapper)

        if ad_service and (global_idx + 1) % 12 == 0 and (global_idx + 1) < len(channels):
            ad_container = ad_service.get_standard_banner_ad()
            if ad_container:
                grid.controls.append(
                    ft.Container(
                        content=ad_container,
                        col=12,
                        alignment=ft.Alignment.CENTER,
                        padding=ft.Padding(0, 5, 0, 5),
                    )
                )

    return grid
