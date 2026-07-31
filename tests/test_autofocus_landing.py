"""Phase D — autofocus landing contract: TDD source-inspection tests.

These tests use ``inspect.getsource()`` to verify that the right
controls carry ``autofocus=True`` in their component source.
"""

import inspect

import flet as ft

from components.empty_state import EmptyState
from hooks.use_autofocus import use_autofocus


def _source(obj) -> str:
    try:
        return inspect.getsource(obj)
    except OSError, TypeError:
        return ""


def _has_autofocus(source: str, control_name: str) -> bool:
    idx = source.find(control_name + "(")
    if idx == -1:
        return False
    window = source[idx : idx + 500]
    return "autofocus=True" in window


def test_onboarding_terms_checkbox_autofocused():
    from screens import onboarding_screen

    source = _source(onboarding_screen)
    assert "ft.Checkbox(" in source
    assert _has_autofocus(source, "ft.Checkbox"), (
        "OnboardingScreen terms Checkbox must carry autofocus=True"
    )


def test_home_add_content_iconbutton_autofocused():
    from components import header

    source = _source(header)
    assert "ft.IconButton(" in source, "Header must render IconButton controls"


def test_local_scan_again_autofocused():
    from screens import local_screen

    source = _source(local_screen)
    assert "on_refresh=_refresh" in source, (
        "LocalScreen must pass on_refresh to Header for the Scan Again action"
    )


def test_settings_switch_autofocused():
    from screens import settings_screen

    source = _source(settings_screen)
    assert _has_autofocus(source, "ft.Switch"), (
        "SettingsScreen Dark Mode Switch must carry autofocus=True"
    )


def test_header_search_textfield_autofocused():
    from screens import search_screen

    source = _source(search_screen)
    assert "ft.TextField(" in source, "SearchScreen must render search TextField"
    assert _has_autofocus(source, "ft.TextField"), (
        "SearchScreen TextField must carry autofocus=True"
    )


def test_empty_state_autofocus_action_propagates():
    es = EmptyState(
        title="X",
        message="Y",
        action_label="Go",
        on_action=lambda e: None,
        autofocus_action=True,
    )
    buttons = [
        c for c in [es] + list(es.content.controls) if isinstance(c, ft.FilledButton)
    ]
    assert buttons, "EmptyState(action_label=...) must render a FilledButton"
    assert buttons[0].autofocus is True, (
        "EmptyState autofocus_action=True must propagate to action FilledButton"
    )


def test_empty_state_default_no_autofocus():
    es = EmptyState(
        title="X",
        message="Y",
        action_label="Go",
        on_action=lambda e: None,
    )
    buttons = [
        c for c in [es] + list(es.content.controls) if isinstance(c, ft.FilledButton)
    ]
    assert buttons
    assert buttons[0].autofocus is False


def test_use_autofocus_hook_exists():
    assert callable(use_autofocus)
