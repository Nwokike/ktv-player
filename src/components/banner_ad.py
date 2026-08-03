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
        from flet_ads.types import NativeAdTemplateType

        from services.ad_service import AdService

        ad_service = AdService(page)
        ad_control = ad_service.get_native_ad(template_type=NativeAdTemplateType.SMALL)
        if ad_control:
            return ad_control
        # Fallback to standard banner if native ad is unavailable
        fallback_ad = ad_service.get_standard_banner_ad()
        if fallback_ad:
            return fallback_ad
        return ft.Container(width=0, height=0)
    except Exception as e:
        logger.debug("Failed to load ad: %s", e)
        return ft.Container(width=0, height=0)
