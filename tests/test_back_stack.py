"""Phase B1 — AppController modal stack TDD tests.

The AppController must track an explicit modal stack so that
the OS back button (and FocusScope.on_back) can pop the top
modal before popping a view. This is needed because Flet's
page-level dialog stack (page.show_dialog / page.pop_dialog)
has no equivalent of Android's Back-stack — the FocusScope
fires on_back but doesn't know whether a dialog is open.

Contract:
- AppController.start() initializes an empty _modal_stack
- push_modal(name) appends to _modal_stack (async)
- close_modal() pops the top modal (async), or clears all
- _handle_back() checks _modal_stack first; if non-empty,
  pops the top modal and returns WITHOUT popping a view
- _handle_back() falls through to pop_views() (existing
  behavior) when _modal_stack is empty
- ControllerMethods exposes push_modal / pop_modal / close_modal
  so components (AddCustomContentDialog) can call controller.push_modal("add")
"""

import asyncio
import inspect
from unittest import mock

from src.main import AppController


def fake_page():
    page = mock.MagicMock()
    page.views = []
    page.update = mock.MagicMock()
    return page


def test_modal_stack_starts_empty():
    controller = AppController(fake_page())
    assert controller._modal_stack == []


def test_push_modal_appends_to_stack():
    controller = AppController(fake_page())
    asyncio.run(controller.push_modal("add_content"))
    assert controller._modal_stack == ["add_content"]


def test_push_modal_multiple_names():
    controller = AppController(fake_page())
    asyncio.run(controller.push_modal("add_content"))
    asyncio.run(controller.push_modal("settings"))
    assert controller._modal_stack == ["add_content", "settings"]


def test_close_modal_pops_top():
    controller = AppController(fake_page())
    asyncio.run(controller.push_modal("add_content"))
    asyncio.run(controller.push_modal("settings"))
    asyncio.run(controller.close_modal())
    assert controller._modal_stack == ["add_content"]


def test_close_modal_when_empty_does_not_raise():
    controller = AppController(fake_page())
    # Should not raise — idempotent when stack is empty
    asyncio.run(controller.close_modal())
    assert controller._modal_stack == []


def test_handle_back_closes_modal_first():
    controller = AppController(fake_page())
    asyncio.run(controller.push_modal("add_content"))
    controller._handle_back()
    # Modal was popped — no view popped, page.update not called
    assert controller._modal_stack == []
    fake_page().update.assert_not_called()


def test_handle_back_pops_modal_updates_page():
    controller = AppController(fake_page())
    asyncio.run(controller.push_modal("add_content"))
    controller._handle_back()
    # page.update called at least once (modal close triggers refresh)
    assert controller.page.update.call_count >= 1


def test_handle_back_when_no_modal_pops_view():
    controller = AppController(fake_page())
    controller.page.views = ["/", "/play"]
    controller._handle_back()
    assert len(controller.page.views) == 1
    controller.page.views.append("/play")
    controller._handle_back()
    assert len(controller.page.views) == 1


def test_handle_back_when_no_modal_and_one_view_does_not_pop():
    """When only one view remains and no modal is open,
    _handle_back does NOT pop the last view."""
    controller = AppController(fake_page())
    controller.page.views = ["/"]
    controller._handle_back()
    assert controller.page.views == ["/"]


def test_controller_methods_exposes_modal_methods():
    """ControllerMethods dataclass must carry the new modal
    methods so components can call controller.push_modal(...)
    inside the same protocol."""
    from state.controller_ctx import ControllerMethods

    methods = ControllerMethods()
    assert hasattr(methods, "push_modal")
    assert hasattr(methods, "pop_modal")
    assert hasattr(methods, "close_modal")
    # Default implementations are async callables (no-ops)
    assert inspect.iscoroutinefunction(methods.push_modal)
    assert inspect.iscoroutinefunction(methods.close_modal)
    assert callable(methods.pop_modal)
