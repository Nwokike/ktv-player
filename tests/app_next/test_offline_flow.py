"""Tests for OfflineFlow component."""

from unittest import mock

import flet as ft

from app_next.components.offline_flow import OfflineFlow


def test_offline_flow_renders_two_buttons():
    flow = OfflineFlow(on_retry=lambda e: None, on_skip=lambda e: None)
    assert isinstance(flow, ft.Container)
    buttons = list(_walk_buttons(flow))
    labels = " ".join(_button_label(b) for b in buttons)
    assert "Retry" in labels
    assert "Offline" in labels


def test_offline_flow_retry_button_wired_to_callback():
    fired = []
    flow = OfflineFlow(
        on_retry=lambda e: fired.append("retry"),
        on_skip=lambda e: None,
    )
    retry_btn = _find_button_by_label(flow, "Retry")
    assert retry_btn is not None
    assert retry_btn.on_click is not None
    retry_btn.on_click(mock.Mock())
    assert fired == ["retry"]


def test_offline_flow_skip_button_wired_to_callback():
    fired = []
    flow = OfflineFlow(
        on_retry=lambda e: None,
        on_skip=lambda e: fired.append("skip"),
    )
    skip_btn = _find_button_by_label(flow, "Offline")
    assert skip_btn is not None
    skip_btn.on_click(mock.Mock())
    assert fired == ["skip"]


# --- helpers ---


def _walk(c):
    """Yield all controls in the tree depth-first."""
    yield c
    children = getattr(c, "controls", None) or []
    if isinstance(children, list):
        for ch in children:
            yield from _walk(ch)
    content = getattr(c, "content", None)
    if content is not None:
        yield from _walk(content)


def _walk_buttons(root):
    for c in _walk(root):
        if isinstance(
            c, (ft.FilledButton, ft.OutlinedButton, ft.ElevatedButton, ft.TextButton)
        ):
            yield c


def _button_label(btn):
    content = btn.content
    if isinstance(content, ft.Text):
        return content.value or ""
    return ""


def _find_button_by_label(root, label_substring):
    for btn in _walk_buttons(root):
        if label_substring in _button_label(btn):
            return btn
    return None
