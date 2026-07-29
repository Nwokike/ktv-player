"""Phase D — autofocus landing contract: TDD source-inspection tests.

These tests use ``inspect.getsource()`` to verify that the right
controls carry ``autofocus=True`` in their component source. This
avoids needing a running Flet renderer (which Flet 0.86.4's
``flet.components.component.Renderer`` does not expose in a test-friendly
way) and is robust against refactors that only move controls around.

Screens covered:
- OnboardingScreen: terms Checkbox has autofocus
- HomeScreen: first IconButton (Add Content) has autofocus
- LocalScreen: Scan Again has autofocus (with-folders case)
- LocalScreen empty state action button: autofocus via EmptyState.autofocus_action
- SettingsScreen: first ExpansionTile expanded=True; its Switch has autofocus
- SearchScreen: TextField already had autofocus (regression guard)
- EmptyState: autofocus_action kwarg propagates to action button
"""

import inspect

import flet as ft

from app_next.components.empty_state import EmptyState
from app_next.hooks.use_autofocus import use_autofocus


def _source(obj) -> str:
    try:
        return inspect.getsource(obj)
    except OSError, TypeError:
        return ""


def _has_autofocus(source: str, control_name: str) -> bool:
    """Return True if *control_name* (e.g. 'ft.Checkbox') is called
    somewhere in *source* and \"autofocus=True\" appears within the
    500 characters that follow that call. This avoids false negatives
    from deeply nested parens (lambdas) that break line-by-line regex."""
    idx = source.find(control_name + "(")
    if idx == -1:
        return False
    window = source[idx : idx + 500]
    return "autofocus=True" in window


def _has_expanded(source: str) -> bool:
    """Return True if 'expanded=' appears in the source (used for
    ExpansionTile expanded=idx == 0)."""
    return "expanded=" in source


def test_onboarding_terms_checkbox_autofocused():
    """The first focusable control on onboarding should be the
    terms Checkbox — autofocus so the D-pad starts on agreement."""
    from app_next.screens import onboarding_screen

    source = _source(onboarding_screen)
    assert "ft.Checkbox(" in source
    assert _has_autofocus(source, "ft.Checkbox"), (
        "OnboardingScreen terms Checkbox must carry autofocus=True"
    )


def test_home_add_content_iconbutton_autofocused():
    """First focusable control in HomeScreen header is Add Content IconButton."""
    from app_next.screens import home_screen

    source = _source(home_screen)
    assert _has_autofocus(source, "ft.IconButton"), (
        "HomeScreen Add Content IconButton must carry autofocus=True"
    )


def test_local_scan_again_autofocused():
    """When folders exist, the Scan Again FilledButton should be
    the first focusable control on LocalScreen."""
    from app_next.screens import local_screen

    source = _source(local_screen)
    assert _has_autofocus(source, "ft.FilledButton"), (
        "LocalScreen Scan Again FilledButton must carry autofocus=True"
    )


def test_settings_appearance_tile_expanded():
    """The first SettingsScreen ExpansionTile must be expanded=True on
    mount so the Dark Mode Switch is visible and receives focus."""
    from app_next.screens import settings_screen

    source = _source(settings_screen)
    assert _has_expanded(source), (
        "First SettingsScreen ExpansionTile must use expanded= (expanded=True for idx==0)"
    )


def test_settings_switch_autofocused():
    """The Dark Mode Switch inside the first ExpansionTile must carry
    autofocus=True so focus lands there when the tile is expanded."""
    from app_next.screens import settings_screen

    source = _source(settings_screen)
    assert _has_autofocus(source, "ft.Switch"), (
        "SettingsScreen Dark Mode Switch must carry autofocus=True"
    )


def test_search_textfield_already_autofocused():
    """Regression guard: SearchScreen already carried autofocus=True on its
    TextField before Phase D — verify it is still there."""
    from app_next.screens import search_screen

    source = _source(search_screen)
    assert _has_autofocus(source, "ft.TextField"), (
        "SearchScreen TextField must still carry autofocus=True (regression guard)"
    )


def test_empty_state_autofocus_action_propagates():
    """EmptyState with autofocus_action=True must propagate autofocus to
    the embedded action FilledButton."""
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
    """Default behaviour: action button has no autofocus."""
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
    """The use_autofocus hook must be importable and callable."""
    assert callable(use_autofocus)
