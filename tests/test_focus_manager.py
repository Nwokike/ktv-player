"""Tests for the focus manager and tab index utilities."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from src.core.focus_manager import (
    _tab_index_counter,
    next_tab_index,
    reset_tab_counter,
)


class TestNextTabIndex:
    def setup_method(self):
        reset_tab_counter()

    def test_starts_at_1(self):
        assert next_tab_index() == 1

    def test_increments_sequentially(self):
        assert next_tab_index() == 1
        assert next_tab_index() == 2
        assert next_tab_index() == 3

    def test_reset(self):
        next_tab_index()
        next_tab_index()
        reset_tab_counter()
        assert next_tab_index() == 1

    def test_wraps_at_max(self):
        reset_tab_counter()
        with patch("src.core.focus_manager._MAX_TAB_INDEX", 3):
            assert next_tab_index() == 1
            assert next_tab_index() == 2
            assert next_tab_index() == 3
            assert next_tab_index() == 2  # wraps to 1, then increments to 2

    def test_unique_values(self):
        values = {next_tab_index() for _ in range(100)}
        assert len(values) == 100


class TestFocusManager:
    def test_set_back_handler(self):
        from src.core.focus_manager import FocusManager

        page = MagicMock()
        fm = FocusManager(page)
        handler = MagicMock()
        fm.set_back_handler(handler)
        assert fm._back_handler is handler

    def test_keyboard_back_triggers_handler(self):
        from src.core.focus_manager import FocusManager

        page = MagicMock()
        fm = FocusManager(page)
        handler = MagicMock()
        fm.set_back_handler(handler)

        event = MagicMock()
        event.key = "Back"
        fm._handle_keyboard(event)
        handler.assert_called_once()

    def test_keyboard_escape_triggers_handler(self):
        from src.core.focus_manager import FocusManager

        page = MagicMock()
        fm = FocusManager(page)
        handler = MagicMock()
        fm.set_back_handler(handler)

        event = MagicMock()
        event.key = "Escape"
        fm._handle_keyboard(event)
        handler.assert_called_once()

    def test_other_key_does_not_trigger(self):
        from src.core.focus_manager import FocusManager

        page = MagicMock()
        fm = FocusManager(page)
        handler = MagicMock()
        fm.set_back_handler(handler)

        event = MagicMock()
        event.key = "Enter"
        fm._handle_keyboard(event)
        handler.assert_not_called()
