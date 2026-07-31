"""Tests for LocalScreen component."""

from screens.local_screen import LocalScreen


def test_local_screen_marked_as_component():
    assert getattr(LocalScreen, "__is_component__", False) is True


def test_local_screen_callable():
    assert callable(LocalScreen)
