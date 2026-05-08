import flet as ft
import asyncio
from core.theme import AppColors
from core.state import state
from channels.provider import channel_provider
from database.manager import db_manager


def build_onboarding_view(page_obj: ft.Page, on_complete: callable) -> ft.View:
    selected_state = {"country": ""}

    terms_checked = ft.Ref[ft.Checkbox]()

    def _palette() -> dict:
        return {
            "page_bg": "background",
            "surface": "surface",
            "surface_variant": "surfaceVariant",
            "text": "onSurface",
            "text_dim": "onSurfaceVariant",
            "border": "outline",
        }

    palette = _palette()

    countries_from_playlist = channel_provider.get_countries()
    if not countries_from_playlist:
        countries_from_playlist = [{"name": "Global"}]
    countries_from_playlist.append({"name": "Other"})

    # --- TV-Ready Country Picker: ListView of focusable ListTiles ---
    country_list = ft.ListView(
        height=220,
        spacing=2,
        padding=ft.Padding(5, 5, 5, 5),
        auto_scroll=False,
    )

    # Track all tiles for selection styling
    all_country_tiles = []

    def select_country(name: str):
        """Handle country selection — update visual state and store value."""
        selected_state["country"] = name
        for tile_info in all_country_tiles:
            is_selected = tile_info["name"] == name
            tile_info["tile"].bgcolor = AppColors.PRIMARY if is_selected else None
            tile_info["tile"].leading = ft.Icon(
                ft.Icons.CHECK_CIRCLE if is_selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
                color=ft.Colors.WHITE if is_selected else palette["text_dim"],
            )
            tile_info["tile"].title = ft.Text(
                tile_info["name"],
                color=ft.Colors.WHITE if is_selected else palette["text"],
                weight=ft.FontWeight.W_500 if is_selected else ft.FontWeight.NORMAL,
            )
        country_list.update()

    def _on_tile_focus(e):
        """Scroll the country list to keep the focused tile visible."""
        control_key = getattr(e.control, "key", None)
        if control_key:
            try:
                country_list.scroll_to(key=control_key, duration=200)
            except Exception:
                pass

    for c in countries_from_playlist:
        cname = c["name"]
        tile = ft.ListTile(
            title=ft.Text(cname, color=palette["text"]),
            leading=ft.Icon(ft.Icons.RADIO_BUTTON_UNCHECKED, color=palette["text_dim"]),
            key=cname,
            on_click=lambda e, name=cname: select_country(name),
            dense=True,
            shape=ft.RoundedRectangleBorder(radius=10),
        )
        # on_focus is not in ListTile.__init__ signature, assign after
        tile.on_focus = _on_tile_focus
        
        all_country_tiles.append({"name": cname, "tile": tile})
        country_list.controls.append(tile)

    country_picker_container = ft.Container(
        content=country_list,
        border=ft.Border.all(1, palette["border"]),
        border_radius=12,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
    )

    async def handle_submit(e):
        if not terms_checked.current.value:
            e.page.snack_bar = ft.SnackBar(
                ft.Text("Please accept the usage agreement to continue."),
                bgcolor=AppColors.WARNING,
            )
            e.page.snack_bar.open = True
            e.page.update()
            return

        country_name = selected_state["country"]
        if not country_name:
            e.page.snack_bar = ft.SnackBar(
                ft.Text("Please select your country."),
                bgcolor=AppColors.WARNING,
            )
            e.page.snack_bar.open = True
            e.page.update()
            return

        await db_manager.set_setting("user_country", country_name)
        await db_manager.set_setting("has_accepted_terms", "true")

        state.user_country = country_name
        state.has_accepted_terms = True
        state.is_first_launch = False

        if asyncio.iscoroutinefunction(on_complete):
            await on_complete()
        else:
            on_complete()

    terms_text = (
        "1. KTV Player is a pure network utility and media rendering engine.\n"
        "2. This application includes a built-in directory of legal, free-to-air public broadcasts.\n"
        "3. You are strictly responsible for ensuring you have the legal right to access any third-party "
        "networks you manually configure within the custom library section of this app."
    )

    content = ft.ListView(
        controls=[
            ft.Container(height=40),
            ft.Column(
                [
                    ft.Image(src="/icon.png", width=100, height=100),
                    ft.Text(
                        "Welcome",
                        size=32,
                        weight=ft.FontWeight.BOLD,
                        color=palette["text"],
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        "A lightning-fast TV player built for seamless network streaming and custom channel addition.",
                        size=16,
                        text_align=ft.TextAlign.CENTER,
                        color=palette["text_dim"],
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            ft.Divider(height=20, color=AppColors.TRANSPARENT),
            ft.Text(
                "Select your Country",
                size=18,
                weight=ft.FontWeight.W_500,
                color=palette["text"],
                text_align=ft.TextAlign.CENTER,
                width=float("inf"),
            ),
            ft.Text(
                "Use ▲ ▼ to browse, press OK to select",
                size=12,
                color=palette["text_dim"],
                text_align=ft.TextAlign.CENTER,
                width=float("inf"),
            ),
            country_picker_container,
            ft.Divider(height=20, color=AppColors.TRANSPARENT),
            ft.Container(
                content=ft.Text(
                    terms_text,
                    size=12,
                    color=palette["text_dim"],
                    text_align=ft.TextAlign.LEFT,
                ),
                padding=15,
                bgcolor=palette["surface"],
                border_radius=10,
            ),
            ft.Row(
                [
                    ft.Checkbox(ref=terms_checked, value=False),
                    ft.Text(
                        "I agree to the Usage Agreement above",
                        size=14,
                        weight=ft.FontWeight.W_500,
                        color=palette["text"],
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=8,
                wrap=True,
            ),
            ft.Divider(height=20, color=AppColors.TRANSPARENT),
            ft.FilledButton(
                content="Start Watching",
                on_click=handle_submit,
                style=ft.ButtonStyle(
                    color="white",
                    bgcolor=AppColors.PRIMARY,
                    padding=20,
                    shape=ft.RoundedRectangleBorder(radius=15),
                ),
                width=float("inf"),
            ),
            ft.Container(height=40),
        ],
        expand=True,
        spacing=10,
        padding=ft.Padding(40, 0, 40, 0),
    )

    return ft.View(
        route="/onboarding",
        controls=[
            ft.Container(
                content=content,
                expand=True,
                bgcolor=palette["page_bg"],
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=0,
    )
