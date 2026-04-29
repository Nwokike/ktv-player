import flet as ft
from core.theme import AppColors, AppTheme


def test_color_tokens():
    assert AppColors.PRIMARY.startswith("#")
    assert AppColors.DARK_BG == "#0F111A"
    assert AppColors.LIGHT_BG == "#F5F7FA"


def test_dark_theme_generation():
    theme = AppTheme.get_dark_theme()
    assert isinstance(theme, ft.Theme)
    assert theme.color_scheme.surface == AppColors.DARK_BG
    assert theme.color_scheme.on_surface == AppColors.DARK_TEXT


def test_light_theme_generation():
    theme = AppTheme.get_light_theme()
    assert isinstance(theme, ft.Theme)
    assert theme.color_scheme.surface == AppColors.LIGHT_BG
    assert theme.color_scheme.on_surface == AppColors.LIGHT_TEXT


def test_dynamic_helpers():
    from unittest.mock import MagicMock

    page = MagicMock()

    # Dark Mode
    page.theme_mode = ft.ThemeMode.DARK
    glass_dark = AppColors.get_glass_bg(page)
    shimmer_dark = AppColors.get_shimmer_base(page)
    assert shimmer_dark == "#1E2132"
    # Flet colors with opacity return a string like 'withOpacity(0.1, white)' or similar depending on flet version
    assert "white" in str(glass_dark).lower() or "ffffff" in str(glass_dark).lower()

    # Light Mode
    page.theme_mode = ft.ThemeMode.LIGHT
    glass_light = AppColors.get_glass_bg(page)
    shimmer_light = AppColors.get_shimmer_base(page)
    assert shimmer_light == "#E2E8F0"
    assert "black" in str(glass_light).lower() or "000000" in str(glass_light).lower()

    assert shimmer_dark != shimmer_light
