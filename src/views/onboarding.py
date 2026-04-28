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
    
    try:
        countries = channel_provider.get_countries()
    except Exception as e:
        print(f"DEBUG: Error getting countries: {e}")
        countries = [{"name": "Global"}]
    
    async def handle_submit(e):
        if not terms_checked.current.value:
            e.page.snack_bar = ft.SnackBar(ft.Text("Please accept the usage agreement to continue."), bgcolor="#F44336")
            e.page.snack_bar.open = True
            e.page.update()
            return
            
        country_name = selected_country.current.value
        if not country_name:
            e.page.snack_bar = ft.SnackBar(ft.Text("Please select your country."), bgcolor="#F44336")
            e.page.snack_bar.open = True
            e.page.update()
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

    # The Self-Contained Legal Agreement (Protects you without external dead links)
    terms_text = (
        "1. KTV Player is a pure network utility and media rendering engine.\n"
        "2. This application includes a built-in directory of legal, free-to-air public broadcasts.\n"
        "3. You are strictly responsible for ensuring you have the legal right to access any third-party "
        "networks you manually configure within the custom library section of this app."
    )

    content = ft.Column([
        ft.Image(src="/icon.png", width=100, height=100),
        ft.Text("Welcome", size=32, weight=ft.FontWeight.BOLD),
        ft.Text(
            "Your ultimate companion for legal streaming. Let's get you set up.",
            size=16,
            text_align=ft.TextAlign.CENTER,
            color="#888888"
        ),
        ft.Divider(height=20, color="transparent"),
        
        ft.Text("Select your Country", size=18, weight=ft.FontWeight.W_500),
        ft.Dropdown(
            ref=selected_country,
            options=[ft.dropdown.Option(c["name"]) for c in countries],
            width=400,
            border_radius=15,
            bgcolor="#F5F5F5" if state.theme_mode == ft.ThemeMode.LIGHT else "#1A1A1A",
        ),
        
        ft.Divider(height=20, color="transparent"),
        
        # Inline Terms of Service Box
        ft.Container(
            content=ft.Text(terms_text, size=12, color="#888888", text_align=ft.TextAlign.LEFT),
            padding=15,
            bgcolor="#F5F5F5" if state.theme_mode == ft.ThemeMode.LIGHT else "#1A1A1A",
            border_radius=10,
            width=400
        ),
        
        ft.Row([
            ft.Checkbox(ref=terms_checked, value=False),
            ft.Text("I agree to the Usage Agreement above", size=14, weight=ft.FontWeight.W_500),
        ], alignment=ft.MainAxisAlignment.CENTER),
        
        ft.Divider(height=20, color="transparent"),
        
        ft.FilledButton(
            content="Start Watching",
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
                alignment=ft.Alignment.CENTER,
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        padding=0,
    )
