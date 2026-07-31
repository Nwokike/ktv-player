"""Tests for FilterBar component — minimal smoke.

FilterBar uses @ft.component with hooks (use_state) so it requires an
active renderer context to be constructed. Full rendering verified in
manual smoke (Task 10). We verify the component wrapper exists and is
callable.
"""

from components.filter_bar import FilterBar


def test_filter_bar_is_component():
    assert getattr(FilterBar, "__is_component__", False) is True
    assert callable(FilterBar)
