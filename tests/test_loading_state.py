"""Tests for LoadingState component."""

import flet as ft

from components.loading_state import LoadingState


def test_loading_state_is_a_container():
    """The component returns a Container with a ProgressRing and Text."""
    state = LoadingState(label="Working...")
    assert isinstance(state, ft.Container)
    # The container wraps a Column [ProgressRing, Text]
    inner = state.content
    assert isinstance(inner, ft.Column)
    types = [type(c) for c in inner.controls]
    assert ft.ProgressRing in types
    assert ft.Text in types


def test_loading_state_uses_label_text():
    state = LoadingState(label="Booting")
    inner = state.content
    texts = [c for c in inner.controls if isinstance(c, ft.Text)]
    assert texts and texts[0].value == "Booting"


def test_loading_state_defaults_label_when_none_given():
    state = LoadingState(label=None)
    inner = state.content
    texts = [c for c in inner.controls if isinstance(c, ft.Text)]
    assert texts and texts[0].value
    assert texts[0].value != "Booting"


def test_loading_state_centered():
    state = LoadingState(label="x")
    assert state.alignment == ft.Alignment(0.0, 0.0)
