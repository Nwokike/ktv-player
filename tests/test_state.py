import pytest
from core.state import AppState

def test_state_initialization():
    s = AppState()
    assert s.is_loading is False
    assert s.user_country == ""
    assert s.has_accepted_terms is False
    assert s.is_first_launch is True
    assert len(s.channels) == 0

def test_history_management():
    s = AppState()
    s.add_to_history("url1")
    assert "url1" in s.history
    
    # Test limit
    for i in range(25):
        s.add_to_history(f"url_{i}")
    assert len(s.history) == 20
    assert s.history[0] == "url_24"

def test_onboarding_state():
    s = AppState()
    s.user_country = "Nigeria"
    s.has_accepted_terms = True
    s.is_first_launch = False
    
    assert s.user_country == "Nigeria"
    assert s.is_first_launch is False
