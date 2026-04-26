import pytest
import flet as ft
from core.theme import AppColors, AppTheme

def test_color_tokens():
    assert AppColors.PRIMARY.startswith("#")
    assert AppColors.BACKGROUND == "#0F111A"

def test_theme_generation():
    theme = AppTheme.get_theme()
    assert isinstance(theme, ft.Theme)
    assert theme.color_scheme.primary == AppColors.PRIMARY
    assert theme.visual_density == ft.VisualDensity.COMFORTABLE
