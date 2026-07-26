"""Offline state UI card for onboarding flow."""

import flet as ft
from core.theme import AppColors


def build_offline_card(page_obj, handle_retry, handle_offline_mode, retry_btn, offline_btn):
    """Build connection failure / offline mode onboarding card."""
    offline_retry_btn = ft.FilledButton(
        ref=retry_btn,
        content="Retry Connection",
        icon=ft.Icons.REFRESH,
        on_click=handle_retry,
        style=ft.ButtonStyle(
            color="white",
            bgcolor=AppColors.PRIMARY,
            padding=ft.Padding(32, 16, 32, 16),
            shape=ft.RoundedRectangleBorder(radius=16),
        ),
        width=320,
    )

    offline_mode_btn = ft.OutlinedButton(
        ref=offline_btn,
        content="Continue to Offline Mode",
        icon=ft.Icons.PLAY_ARROW_ROUNDED,
        on_click=handle_offline_mode,
        style=ft.ButtonStyle(
            color=AppColors.PRIMARY,
            padding=ft.Padding(32, 16, 32, 16),
            shape=ft.RoundedRectangleBorder(radius=16),
            side=ft.BorderSide(2, AppColors.PRIMARY),
        ),
        width=320,
    )

    return ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(
                        ft.Icons.WIFI_OFF_ROUNDED,
                        size=48,
                        color=AppColors.PRIMARY,
                    ),
                    bgcolor=ft.Colors.with_opacity(0.1, AppColors.PRIMARY),
                    padding=20,
                    border_radius=50,
                ),
                ft.Container(height=10),
                ft.Text(
                    "Connection Required",
                    size=22,
                    weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "KTV Player needs an active internet connection to download the initial TV playlist and complete setup. "
                    "Please check your Wi-Fi or mobile data.",
                    size=14,
                    text_align=ft.TextAlign.CENTER,
                    color=AppColors.GREY_DIM,
                    width=340,
                ),
                ft.Container(height=15),
                offline_retry_btn,
                ft.Container(height=5),
                offline_mode_btn,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
        ),
        padding=24,
        bgcolor=AppColors.get_surface(page_obj),
        border_radius=24,
        border=ft.Border.all(0.5, AppColors.get_border_color(page_obj)),
        alignment=ft.Alignment.CENTER,
        margin=ft.Margin(16, 16, 16, 16),
    )
