import flet as ft
from core.state import state
from core.theme import AppColors
from channels.provider import channel_provider
from database.manager import db_manager

def OnboardingView(on_complete: callable):
    selected_country = ft.Ref[ft.Dropdown]()
    terms_checked = ft.Ref[ft.Checkbox]()
    
    countries = channel_provider.get_countries()
    
    async def handle_submit(e):
        if not terms_checked.current.value:
            page = e.page
            page.show_snack_bar(ft.SnackBar(ft.Text("Please accept the terms to continue.")))
            return
            
        country_name = selected_country.current.value
        if not country_name:
            e.page.show_snack_bar(ft.SnackBar(ft.Text("Please select your country.")))
            return
            
        # Save settings
        await db_manager.set_setting("user_country", country_name)
        await db_manager.set_setting("has_accepted_terms", "true")
        
        state.user_country = country_name
        state.has_accepted_terms = True
        state.is_first_launch = False
        
        await on_complete()

    return ft.Column([
        ft.Image(src="icon.png", width=100, height=100),
        ft.Text("Welcome to KTV Player", size=28, weight=ft.FontWeight.BOLD),
        ft.Text(
            "Your ultimate companion for legal streaming. Let's get you set up.",
            size=16,
            text_align=ft.TextAlign.CENTER,
            color=ft.Colors.GREY_700
        ),
        ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
        
        ft.Text("Select your Country", size=18, weight=ft.FontWeight.W_600),
        ft.Dropdown(
            ref=selected_country,
            options=[ft.dropdown.Option(c["name"]) for c in countries],
            width=300,
            border_radius=10,
            bgcolor=ft.Colors.GREY_100,
            leading_icon=ft.Icons.LOCATION_ON,
        ),
        
        ft.Row([
            ft.Checkbox(ref=terms_checked, value=False),
            ft.Text("I agree to the Terms of Service", size=14),
        ], alignment=ft.MainAxisAlignment.CENTER),
        
        ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
        
        ft.Button(
            "Start Watching",
            on_click=handle_submit,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=AppColors.PRIMARY,
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
            width=250,
        )
    ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
