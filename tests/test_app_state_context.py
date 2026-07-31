"""Tests for the AppStateCtx adapter."""

from core.state import state as core_singleton
from state.app_state import AppStateCtx


def test_app_state_context_resolves_to_core_singleton():
    """The default value of AppStateCtx is the core.state module singleton."""
    # create_context stores the default value at .default_value
    assert AppStateCtx.default_value is core_singleton


def test_app_state_context_default_value_is_observable():
    """The resolved default is the @ft.observable state singleton."""
    from flet.components.observable import Observable

    assert isinstance(AppStateCtx.default_value, Observable)
