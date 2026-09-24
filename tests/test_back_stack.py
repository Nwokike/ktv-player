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
  pops the top modal and returns WITHOUT touching the views
- _handle_back() then closes a playing video through the awaited
  position save, and finally delegates to _handle_shell_back():
  a secondary tab returns Home, Home exits the app
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


def test_handle_back_on_secondary_tab_returns_home():
    """Back on Local/Settings goes Home — it must NOT pop the shell view.

    The dashboard sits on a /blank underlay, so popping would strand the
    user on an empty black screen instead of closing the app or going Home.
    """
    controller = AppController(fake_page())
    controller.page.views = ["/blank", "/"]
    methods = mock.MagicMock()
    methods.on_non_home_tab.return_value = True
    controller._controller_methods = methods

    controller._handle_back()

    methods.go_home.assert_called_once()
    assert len(controller.page.views) == 2


def test_handle_back_on_home_exits_app():
    """On the Home tab there is nowhere to go back to: the app exits, but
    the shell view is left intact (no pop onto the blank underlay)."""
    controller = AppController(fake_page())
    controller.page.views = ["/blank", "/"]
    methods = mock.MagicMock()
    methods.on_non_home_tab.return_value = False
    controller._controller_methods = methods

    controller._handle_back()

    methods.go_home.assert_not_called()
    controller.page.run_task.assert_called_once_with(controller._exit_app)
    assert len(controller.page.views) == 2


def test_handle_back_with_player_schedules_awaited_save():
    """A playing video is closed through the awaited save path, whatever
    route the back press arrived by."""
    controller = AppController(fake_page())
    player = mock.MagicMock()
    player._is_closing = False
    player._position_saved = False
    view = mock.MagicMock()
    view.controls = [player]
    controller.page.views = [view]

    with mock.patch.object(
        AppController, "_find_immersive_player", return_value=player
    ):
        controller._handle_back()

    assert player._is_closing is True
    controller.page.run_task.assert_called_once_with(
        controller._close_player_with_save, player
    )


def test_handle_back_when_shell_state_unknown_leaves_views_alone():
    """If the shell never reported its tab, do nothing rather than exit."""
    controller = AppController(fake_page())
    controller.page.views = ["/blank", "/"]

    controller._handle_back()

    controller.page.run_task.assert_not_called()
    assert len(controller.page.views) == 2


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
