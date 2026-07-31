"""Tests for OfflineFlow component."""

from unittest import mock

import flet as ft
from flet_tree import button_label, find_button_by_label, walk_buttons

from components.offline_flow import OfflineFlow


def test_offline_flow_renders_two_buttons():
    flow = OfflineFlow(on_retry=lambda e: None, on_skip=lambda e: None)
    assert isinstance(flow, ft.Container)
    buttons = list(walk_buttons(flow))
    labels = " ".join(button_label(b) for b in buttons)
    assert "Retry" in labels
    assert "Offline" in labels


def test_offline_flow_retry_button_wired_to_callback():
    fired = []
    flow = OfflineFlow(
        on_retry=lambda e: fired.append("retry"),
        on_skip=lambda e: None,
    )
    retry_btn = find_button_by_label(flow, "Retry")
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
    skip_btn = find_button_by_label(flow, "Offline")
    assert skip_btn is not None
    skip_btn.on_click(mock.Mock())
    assert fired == ["skip"]
