"""Tests for the M1 placeholder screen."""

import flet as ft

from app_next.screens.placeholder_screen import PlaceholderScreen


def test_placeholder_is_container_with_named_text():
    p = PlaceholderScreen(name="Home")
    assert isinstance(p, ft.Container)
    inner = p.content
    assert isinstance(inner, ft.Column)
    texts = [c for c in inner.controls if isinstance(c, ft.Text)]
    assert any("Home" in (t.value or "") for t in texts)
