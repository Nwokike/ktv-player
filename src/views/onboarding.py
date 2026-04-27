import flet as ft
import asyncio
from core.theme import AppColors
from core.state import state
from core.theme import AppColors
from channels.provider import channel_provider
from database.manager import db_manager

def build_onboarding_view(on_complete: callable) -> ft.View:
    """Builds the onboarding view."""
    print("DEBUG: Building Onboarding View")
    
    selected_country = ft.Ref[ft.Dropdown]()
    terms_checked = ft.Ref[ft.Checkbox]()
    
    try:
        countries = channel_provider.get_countries()
    except Exception as e:
        print(f"DEBUG: Error getting countries: {e}")
        countries = [{"name": "Global"}]
    
    async def handle_submit(e):
        if not terms_checked.current.value:
            e.page.show_dialog(ft.SnackBar(ft.Text("Please accept the terms to continue.")))
            return
            
        country_name = selected_country.current.value
        if not country_name:
            e.page.show_dialog(ft.SnackBar(ft.Text("Please select your country.")))
            return
            
        # Save settings
        await db_manager.set_setting("user_country", country_name)
        await db_manager.set_setting("has_accepted_terms", "true")
        
        state.user_country = country_name
        state.has_accepted_terms = True
        state.is_first_launch = False
        
        if asyncio.iscoroutinefunction(on_complete):
            await on_complete()
        else:
            on_complete()

    content = ft.Column([
        ft.Image(src="/icon.png", width=100, height=100),
        ft.Text("Welcome", size=32, weight=ft.FontWeight.BOLD),
        ft.Text(
            "Your ultimate companion for legal streaming. Let's get you set up.",
            size=16,
            text_align=ft.TextAlign.CENTER,
            color=ft.Colors.ON_SURFACE_VARIANT
        ),
        ft.Divider(height=40, color=ft.Colors.TRANSPARENT),
        
        ft.Text("Select your Country", size=18, weight=ft.FontWeight.W_500),
        ft.Dropdown(
            ref=selected_country,
            options=[ft.dropdown.Option(c["name"]) for c in countries],
            width=400,
            border_radius=15,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        ),
        
        ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
        
        ft.Row([
            ft.Checkbox(ref=terms_checked, value=False),
            ft.Text("I agree to the Terms of Service & Privacy Policy", size=14),
        ], alignment=ft.MainAxisAlignment.CENTER),
        
        ft.Text(
            "Disclaimer: KTV Player is a general-purpose player. We are not responsible for any 3rd party content you add.",
            size=12,
            italic=True,
            text_align=ft.TextAlign.CENTER,
            color=ft.Colors.ON_SURFACE_VARIANT
        ),
        
        ft.Divider(height=40, color=ft.Colors.TRANSPARENT),
        
        ft.FilledButton(
            "Start Watching",
            on_click=handle_submit,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=AppColors.PRIMARY,
                padding=20,
                shape=ft.RoundedRectangleBorder(radius=15),
            ),
            width=300,
        )
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)

    return ft.View(
        route="/onboarding",
        controls=[
            ft.Container(
                content=content,
                expand=True,
                padding=40,
                bgcolor=ft.Colors.SURFACE,
                alignment=ft.Alignment(0, 0),
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=0,
    )

