"""Tests for LoadingState component (Shimmer skeleton, TV-UX wave 1)."""

import flet as ft

from components.loading_state import LoadingState


def _walk(c, seen=None):
    if seen is None:
        seen = []
    if c is None or id(c) in seen:
        return seen
    seen.append(c)
    seen.append(id(c))
    for attr in ("content", "controls"):
        child = getattr(c, attr, None)
        if isinstance(child, (list, tuple)):
            for ch in child:
                _walk(ch, seen)
        else:
            _walk(child, seen)
    return seen


def test_loading_state_is_a_container_with_shimmer_and_text():
    """The component returns a Container wrapping Column [Shimmer, Text]."""
    state = LoadingState(label="Working...")
    assert isinstance(state, ft.Container)
    inner = state.content
    assert isinstance(inner, ft.Column)
    types = [type(c) for c in inner.controls]
    assert ft.Shimmer in types
    assert ft.Text in types


def test_loading_state_has_no_progress_ring():
    """Spinners were replaced by skeleton placeholders."""
    assert not any(isinstance(c, ft.ProgressRing) for c in _walk(LoadingState()))


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


def test_loading_state_shimmer_has_skeleton_cards():
    shimmer = next(c for c in _walk(LoadingState()) if isinstance(c, ft.Shimmer))
    assert isinstance(shimmer.content, ft.Column)
    assert len(shimmer.content.controls) == 3
