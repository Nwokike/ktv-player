"""BannerAd component wrapper — Colab-style glassmorphic banner ad."""

import logging

import flet as ft
from flet import Control

logger = logging.getLogger(__name__)


def build_banner_ad(page: ft.Page | None, unit_id: str | None = None) -> Control:
    """Build a glass-container-wrapped banner ad (mobile only)."""
    if not page or not hasattr(page, "platform"):
        return ft.Container(width=0, height=0)

    try:
        if not page.platform.is_mobile():
            return ft.Container(width=0, height=0)
    except Exception:
        return ft.Container(width=0, height=0)

    try:
        import flet_ads as fta

        from services.ad_service import AdService

        if not unit_id:
            ad_service = AdService(page)
            unit_id = ad_service.get_banner_unit_id()

        ad = fta.BannerAd(
            unit_id=unit_id,
            width=320,
            height=50,
            on_error=lambda e: logger.debug("Banner ad error: %s", e),
        )
    except Exception as e:
        logger.debug("Failed to load BannerAd: %s", e)
        return ft.Container(width=0, height=0)

    return ft.Container(
        content=ft.Column(
            [
                ad,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
        alignment=ft.Alignment.CENTER,
        padding=6,
        border_radius=12,
        bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
        margin=ft.Margin(12, 4, 12, 4),
    )
