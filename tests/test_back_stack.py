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


# -- View.controls is not always a list -------------------------------------
# A device log captured the crash this guards:
#   main.py view_pop -> _player_in_top_view
#   TypeError: 'Component' object is not iterable
# Flet types View.controls as a list, but hands back a bare Component when a
# view has a single child, and iterating that kills the back press.


class _SingleChildView:
    def __init__(self, child):
        self.controls = child
        self.route = "/"


def test_view_children_normalises_a_single_component():
    child = mock.MagicMock()
    assert AppController._view_children(_SingleChildView(child)) == [child]


def test_view_children_passes_through_a_list():
    children = [mock.MagicMock(), mock.MagicMock()]
    view = mock.MagicMock()
    view.controls = children
    assert AppController._view_children(view) == children


def test_view_children_handles_a_view_with_none():
    view = mock.MagicMock()
    view.controls = None
    assert AppController._view_children(view) == []


def test_back_press_does_not_crash_on_a_single_child_view():
    """The regression, end to end: a back press with a non-list view."""
    controller = AppController(fake_page())
    player = mock.MagicMock()
    player._is_closing = False
    player._position_saved = False
    view = _SingleChildView(player)
    view.route = "/play"
    controller.page.views = [view]

    with mock.patch.object(
        AppController, "_find_immersive_player", return_value=player
    ):
        controller._handle_back()  # must not raise

    assert player._is_closing is True


def test_push_modal_duplicate_top_is_noop():
    """Pushing the same modal twice doesn't duplicate the tracker or update."""
    from unittest import mock

    controller = AppController(fake_page())
    asyncio.run(controller.push_modal("add_content"))
    with mock.patch.object(controller.page, "update") as upd:
        asyncio.run(controller.push_modal("add_content"))
    assert controller._modal_stack == ["add_content"]
    upd.assert_not_called()


def test_close_modal_empty_is_noop_without_update():
    """Empty close does nothing AND doesn't touch the page."""
    from unittest import mock

    controller = AppController(fake_page())
    with mock.patch.object(controller.page, "update") as upd:
        asyncio.run(controller.close_modal())
    upd.assert_not_called()


def test_pop_modal_missing_name_is_noop():
    """Removing an absent name doesn't mutate or update."""
    from unittest import mock

    controller = AppController(fake_page())
    asyncio.run(controller.push_modal("add_content"))
    with mock.patch.object(controller.page, "update") as upd:
        asyncio.run(controller.pop_modal("nope"))
    assert controller._modal_stack == ["add_content"]
    upd.assert_not_called()


def test_cdn_headers_merge_per_key():
    """Override keys fill gaps; caller-supplied keys survive."""
    from src.main import CDN_HEADER_OVERRIDES, merge_cdn_headers

    assert CDN_HEADER_OVERRIDES, "expected at least one CDN override in constants"
    probe_url = None
    probe_hdrs = None
    for pattern, hdrs in CDN_HEADER_OVERRIDES.items():
        probe_url = f"https://{pattern}/stream.m3u8"
        probe_hdrs = hdrs
        break

    merged, referer = merge_cdn_headers(
        probe_url, {"User-Agent": "UA", "X-Keep": "yes"}, None
    )
    assert merged["User-Agent"] == "UA"
    assert merged["X-Keep"] == "yes"
    for k, v in probe_hdrs.items():
        if k not in ("User-Agent",):
            assert merged[k] == v
    if "Referer" in probe_hdrs:
        assert referer == probe_hdrs["Referer"]

    # Explicit referer wins over the override default.
    _, referer2 = merge_cdn_headers(probe_url, {}, "https://mine.example/")
    assert referer2 == "https://mine.example/"

    # Non-matching URL passes headers through untouched.
    merged3, _ = merge_cdn_headers("https://example.com/s.m3u8", {"A": "b"}, None)
    assert merged3 == {"A": "b"}
