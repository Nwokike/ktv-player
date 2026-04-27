import flet as ft
from flet_lottie import Lottie
from core.theme import AppColors

def SplashView():
    print("Creating SplashView...")
    # This view will display a Lottie animation for 3 seconds
    
    # Use the official logo
    logo = ft.Image(
        src="icon.png",
        width=150,
        height=150,
        fit="contain",
    )

    return ft.Column([
        logo,
        ft.Text("KTV PLAYER", size=32, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY),
        ft.Text("Immersive High-Speed Rendering", size=16, color=ft.Colors.GREY_700),
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20)
