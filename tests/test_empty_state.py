"""Tests for EmptyState component."""

import flet as ft

from app_next.components.empty_state import EmptyState


def test_empty_state_is_container():
    es = EmptyState(
        title="Nothing here", message="Try different filters", action_label=None
    )
    assert isinstance(es, ft.Container)


def test_empty_state_shows_title_and_message():
    es = EmptyState(
        title="No results", message="Try a different search", action_label=None
    )
    texts = list(_walk_texts(es))
    assert any("No results" in (t.value or "") for t in texts)
    assert any("Try a different" in (t.value or "") for t in texts)


def test_empty_state_shows_action_button_when_label_provided():
    action_fired = []

    def on_action(e):
        action_fired.append(1)

    es = EmptyState(
        title="No videos",
        message="Scan your device",
        action_label="Scan Now",
        on_action=on_action,
    )
    buttons = list(_walk_buttons(es))
    assert len(buttons) >= 1
    buttons[0].on_click(None)
    assert action_fired == [1]


def test_empty_state_hides_action_when_label_is_none():
    es = EmptyState(title="x", message="y", action_label=None)
    buttons = list(_walk_buttons(es))
    assert buttons == []


# helpers
def _walk(c):
    yield c
    children = getattr(c, "controls", None) or []
    if isinstance(children, list):
        for ch in children:
            yield from _walk(ch)
    content = getattr(c, "content", None)
    if content:
        yield from _walk(content)


def _walk_texts(c):
    for x in _walk(c):
        if isinstance(x, ft.Text):
            yield x


def _walk_buttons(c):
    for x in _walk(c):
        if isinstance(x, (ft.FilledButton, ft.OutlinedButton, ft.ElevatedButton)):
            yield x
