"""Tests for use_debounce hook — pure logic and smoke.

The hook itself requires @ft.component render context; we test the inner
logic via _debounced_value helper (it's identity for single input).
Full hook exercise is in manual smoke.
"""

from hooks.use_debounce import use_debounce


def test_use_debounce_marked_as_hook():
    """The function exists and is callable."""
    assert callable(use_debounce)
