"""Tests for SettingsScreen component."""

from screens.settings_screen import _SECTIONS, SettingsScreen


def test_settings_screen_marked_as_component():
    assert getattr(SettingsScreen, "__is_component__", False) is True


def test_sections_have_6_entries():
    assert len(_SECTIONS) == 6


def test_sections_cover_expected_keys():
    keys = {s["key"] for s in _SECTIONS}
    expected = {
        "appearance",
        "localization",
        "data_management",
        "custom_content",
        "premium",
        "about",
    }
    assert keys == expected
