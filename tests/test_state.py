import flet as ft
from core.state import AppState


def test_state_initialization():
    s = AppState()
    assert s.is_loading is False
    assert s.user_country == ""
    assert s.has_accepted_terms is False
    assert s.is_first_launch is True
    assert len(s.channels) == 0
    assert s.theme_mode == ft.ThemeMode.SYSTEM


def test_history_management():
    s = AppState()
    # Test basic add
    s.add_to_history("url1")
    assert s.history == ["url1"]

    # Test moving to front
    s.add_to_history("url2")
    s.add_to_history("url1")
    assert s.history == ["url1", "url2"]

    # Test limit (20)
    for i in range(25):
        s.add_to_history(f"url_{i}")
    assert len(s.history) == 20
    assert s.history[0] == "url_24"
    assert "url_4" not in s.history  # Should have been evicted (25 items added, 0-4 are oldest)


def test_onboarding_state():
    s = AppState()
    s.user_country = "Nigeria"
    s.has_accepted_terms = True
    s.is_first_launch = False

    assert s.user_country == "Nigeria"
    assert s.is_first_launch is False


def test_state_reset_fields():
    # Verify that __init__ correctly resets collections
    s = AppState()
    s.channels = [{"name": "Test"}]
    s.favorites = ["fav1"]
    s.categorized_channels = {"Cat": []}
    s.country_channels = {"Country": []}

    s.__init__()
    assert len(s.channels) == 0
    assert len(s.favorites) == 0
    assert len(s.categorized_channels) == 0
    assert len(s.country_channels) == 0
