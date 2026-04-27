import flet as ft
from core.state import state
from core.theme import AppColors
from channels.provider import channel_provider
from database.manager import db_manager

class OnboardingView(ft.Container):
    def __init__(self, on_complete: callable):
        super().__init__()
        self.on_complete = on_complete
        self.expand = True
        self.bgcolor = ft.Colors.SURFACE
        self.padding = 40
        
        self.selected_country = ft.Ref[ft.Dropdown]()
        self.terms_checked = ft.Ref[ft.Checkbox]()
        
        countries = channel_provider.get_countries()
        
        self.content = ft.Column([
            ft.Image(src="icon.png", width=100, height=100),
            ft.Text("Welcome to KTV Player", style=ft.TextThemeStyle.HEADLINE_LARGE, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Your ultimate companion for legal streaming. Let's get you set up.",
                style=ft.TextThemeStyle.BODY_LARGE,
                text_align=ft.TextAlign.CENTER,
                color=ft.Colors.ON_SURFACE_VARIANT
            ),
            ft.Divider(height=40, color=ft.Colors.TRANSPARENT),
            
            ft.Text("Select your Country", style=ft.TextThemeStyle.TITLE_MEDIUM),
            ft.Dropdown(
                ref=self.selected_country,
                options=[ft.dropdown.Option(c["name"]) for c in countries],
                width=400,
                border_radius=15,
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                leading_icon=ft.Icons.LOCATION_ON,
            ),
            
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            
            ft.Row([
                ft.Checkbox(ref=self.terms_checked, value=False),
                ft.Text("I agree to the Terms of Service & Privacy Policy", style=ft.TextThemeStyle.BODY_MEDIUM),
            ], alignment=ft.MainAxisAlignment.CENTER),
            
            ft.Text(
                "Disclamer: KTV Player is a general-purpose player. We are not responsible for any 3rd party content you add.",
                style=ft.TextThemeStyle.BODY_SMALL,
                italic=True,
                text_align=ft.TextAlign.CENTER,
                color=ft.Colors.ON_SURFACE_VARIANT
            ),
            
            ft.Divider(height=40, color=ft.Colors.TRANSPARENT),
            
            ft.ElevatedButton(
                "Start Watching",
                on_click=self.handle_submit,
                style=ft.ButtonStyle(
                    color=ft.Colors.WHITE,
                    bgcolor=AppColors.PRIMARY,
                    padding=20,
                    shape=ft.RoundedRectangleBorder(radius=15),
                ),
                width=300,
            )
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)

    async def handle_submit(self, e):
        if not self.terms_checked.current.value:
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Please accept the terms to continue.")))
            return
            
        country_name = self.selected_country.current.value
        if not country_name:
            self.page.show_snack_bar(ft.SnackBar(ft.Text("Please select your country.")))
            return
            
        # Save settings
        await db_manager.set_setting("user_country", country_name)
        await db_manager.set_setting("has_accepted_terms", "true")
        
        state.user_country = country_name
        state.has_accepted_terms = True
        state.is_first_launch = False
        
        if asyncio.iscoroutinefunction(self.on_complete):
            await self.on_complete()
        else:
            self.on_complete()

import asyncio
