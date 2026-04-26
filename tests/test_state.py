import pytest
from core.state import AppState

def test_state_initialization():
    s = AppState()
    assert s.current_url == ""
    assert s.is_loading is False
    assert len(s.history) == 0

def test_history_limit():
    s = AppState()
    for i in range(30):
        s.add_to_history(f"url_{i}")
    
    assert len(s.history) == 20
    assert s.history[0] == "url_29"
