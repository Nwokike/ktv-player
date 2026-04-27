import flet as ft
from core.state import state
from core.theme import AppColors
from channels.provider import channel_provider
from database.manager import db_manager

def OnboardingView(on_complete: callable):
    return ft.Container(
        content=ft.Column([
            ft.Text("Onboarding Test", size=30, weight="bold"),
            ft.Button("Complete", on_click=lambda _: e.page.run_task(on_complete()))
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=40,
        bgcolor=ft.Colors.YELLOW, # Bright color to see if it renders
    )
