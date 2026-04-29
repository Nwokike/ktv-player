import flet as ft
import asyncio
from core.theme import AppColors
from core.state import state
from channels.provider import channel_provider
from database.manager import db_manager


def build_onboarding_view(on_complete: callable) -> ft.View:
    """Builds the onboarding view."""
    print("DEBUG: Building Onboarding View")

    selected_country = ft.Ref[ft.Dropdown]()
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

    try:
        countries = channel_provider.get_countries()
        countries.append({"name": "Other"})
    except Exception as e:
        print(f"DEBUG: Error getting countries: {e}")
        countries = [{"name": "Global"}, {"name": "Other"}]

    async def handle_submit(e):
        if not terms_checked.current.value:
            e.page.snack_bar = ft.SnackBar(
                ft.Text("Please accept the usage agreement to continue."),
                bgcolor=AppColors.WARNING,
            )
            e.page.snack_bar.open = True
            e.page.update()
            return

        country_name = selected_country.current.value
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

    content = ft.Column(
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
            ft.Divider(height=20, color=AppColors.TRANSPARENT),
            ft.Text(
                "Select your Country",
                size=18,
                weight=ft.FontWeight.W_500,
                color=palette["text"],
            ),
            ft.Dropdown(
                ref=selected_country,
                options=[ft.dropdown.Option(c["name"]) for c in countries],
                expand=True,
                border_radius=15,
                filled=True,
                fill_color=palette["surface_variant"],
                bgcolor=palette["surface_variant"],
                color=palette["text"],
                text_style=ft.TextStyle(color=palette["text"]),
                hint_style=ft.TextStyle(color=palette["text_dim"]),
                border=ft.InputBorder.OUTLINE,
                border_color=palette["border"],
                focused_border_color=AppColors.PRIMARY,
                content_padding=ft.Padding.symmetric(horizontal=16, vertical=14),
                menu_style=ft.MenuStyle(bgcolor=palette["surface_variant"]),
                text_align=ft.TextAlign.START,
            ),
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
                # FIX 1: Removed 'expand=True' from this Container.
                # This stops it from clipping against the Column, allowing all 3 lines to show!
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
                    color="white",  # String literal fallback to avoid Enum crash
                    bgcolor=AppColors.PRIMARY,
                    padding=20,
                    shape=ft.RoundedRectangleBorder(radius=15),
                ),
                expand=True,
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        spacing=10,
        tight=True,
    )

    return ft.View(
        route="/onboarding",
        controls=[
            ft.Container(
                content=content,
                expand=True,
                padding=40,
                bgcolor=palette["page_bg"],
                alignment=ft.Alignment.CENTER,
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=0,
    )
