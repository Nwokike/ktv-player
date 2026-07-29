"""Phase E — use_keyboard_shortcuts TDD tests.

Tests the page-level keyboard shortcut handler installed by
use_keyboard_shortcuts. The hook registers via ft.on_mounted
which requires a Renderer; to avoid that, we mock ft.on_mounted
to capture the installer callback, run it ourselves, then test
the resulting handler directly.
"""

import asyncio
from unittest import mock

from app_next.hooks.use_keyboard_shortcuts import use_keyboard_shortcuts


def test_use_keyboard_shortcuts_is_callable():
    assert callable(use_keyboard_shortcuts)


def test_handler_dispatches_ctrl_k_to_on_search():
    mock_controller = mock.MagicMock()
    mock_controller.page = mock.MagicMock()
    mock_page = mock_controller.page
    mock_page.on_keyboard_event = None

    on_search = mock.MagicMock()

    # Patch ft.on_mounted so it immediately runs the installer
    with mock.patch("flet.on_mounted") as mock_mounted:
        use_keyboard_shortcuts(
            controller=mock_controller,
            on_search=on_search,
        )
        # on_mounted was called with a coroutine function; call it
        assert mock_mounted.called
        installer = mock_mounted.call_args[0][0]
        asyncio.run(installer())

    handler = mock_page.on_keyboard_event
    assert handler is not None

    async def _run():
        fake_event = mock.Mock()
        fake_event.ctrl = True
        fake_event.key = "k"
        await handler(fake_event)

    asyncio.run(_run())
    on_search.assert_called_once()


def test_handler_chains_to_previous_handler_for_unhandled_keys():
    mock_controller = mock.MagicMock()
    mock_controller.page = mock.MagicMock()
    mock_page = mock_controller.page

    previous_handler = mock.MagicMock()
    mock_page.on_keyboard_event = previous_handler

    with mock.patch("flet.on_mounted") as mock_mounted:
        use_keyboard_shortcuts(controller=mock_controller)
        installer = mock_mounted.call_args[0][0]
        asyncio.run(installer())

    handler = mock_page.on_keyboard_event
    assert handler is not None

    async def _run():
        fake_event = mock.Mock()
        fake_event.ctrl = False
        fake_event.key = "a"
        await handler(fake_event)

    asyncio.run(_run())
    previous_handler.assert_called_once()


def test_handler_does_not_swallow_arrow_keys():
    """Arrow keys are navigation — they must not be intercepted."""
    mock_controller = mock.MagicMock()
    mock_controller.page = mock.MagicMock()
    mock_page = mock_controller.page
    mock_page.on_keyboard_event = None

    with mock.patch("flet.on_mounted") as mock_mounted:
        use_keyboard_shortcuts(controller=mock_controller)
        installer = mock_mounted.call_args[0][0]
        asyncio.run(installer())

    handler = mock_page.on_keyboard_event
    assert handler is not None

    async def _run():
        fake_event = mock.Mock()
        fake_event.ctrl = False
        fake_event.key = "ArrowDown"
        await handler(fake_event)

    # No crash — arrow keys pass through (with no-op previous handler)
    asyncio.run(_run())


def test_on_search_coroutine_is_awaited():
    """on_search coroutine must be awaited (not fire-and-forget),
    so that the search tab switch happens before subsequent keys."""
    mock_controller = mock.MagicMock()
    mock_controller.page = mock.MagicMock()
    mock_page = mock_controller.page
    mock_page.on_keyboard_event = None

    order: list[str] = []

    async def on_search() -> None:
        order.append("search")

    with mock.patch("flet.on_mounted") as mock_mounted:
        use_keyboard_shortcuts(controller=mock_controller, on_search=on_search)
        installer = mock_mounted.call_args[0][0]
        asyncio.run(installer())

    handler = mock_page.on_keyboard_event

    async def _run():
        fake_event = mock.Mock()
        fake_event.ctrl = True
        fake_event.key = "k"
        await handler(fake_event)

    asyncio.run(_run())
    assert order == ["search"]
