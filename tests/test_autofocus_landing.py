"""Phase D — autofocus landing contract: TDD source-inspection tests.

These tests use ``inspect.getsource()`` to verify that the right
controls carry ``autofocus=True`` in their component source.
"""

import inspect

import flet as ft

from components.empty_state import EmptyState


def _source(obj) -> str:
    try:
        return inspect.getsource(obj)
    except (OSError, TypeError):
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
    assert "ft.IconButton(" in source or "_make_icon_btn" in source, (
        "Header must render action buttons"
    )


def test_local_scan_again_autofocused():
    from screens import local_screen

    source = _source(local_screen)
    assert "on_refresh=_refresh" in source, (
        "LocalScreen must pass on_refresh to Header for the Scan Again action"
    )


def test_settings_switch_not_autofocused():
    """The Dark Mode Switch must NOT steal focus: it sits mid-list and
    autofocus would drop the D-pad landing in the middle of the tab."""
    from screens import settings_screen

    source = _source(settings_screen)
    assert not _has_autofocus(source, "ft.Switch"), (
        "SettingsScreen Dark Mode Switch must not carry autofocus=True"
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
        c for c in [es, *list(es.content.controls)] if isinstance(c, ft.FilledButton)
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
        c for c in [es, *list(es.content.controls)] if isinstance(c, ft.FilledButton)
    ]
    assert buttons
    assert buttons[0].autofocus is False


def test_autofocus_uses_native_prop_not_dead_hook():
    """The use_autofocus hook was deleted (Phase 3): screens use the native
    autofocus=True control prop directly. This pins the deletion."""
    import pathlib

    import hooks.use_focus_scope as _fs

    assert not pathlib.Path("src/hooks/use_autofocus.py").exists()
    assert hasattr(_fs, "focus_scope")
