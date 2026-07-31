"""Phase E — use_keyboard_shortcuts TDD tests.

Tests the page-level keyboard shortcut handler installed by
use_keyboard_shortcuts. The hook registers via ft.on_mounted
which requires a Renderer; to avoid that, we mock ft.on_mounted
to capture the installer callback, run it ourselves, then test
the resulting handler directly.
"""

import asyncio
from unittest import mock

import flet.controls.context as _flet_ctx

from hooks.use_keyboard_shortcuts import use_keyboard_shortcuts


def test_use_keyboard_shortcuts_is_callable():
    assert callable(use_keyboard_shortcuts)


def _mock_context_page():
    """Patch Context.page at the class level with a PropertyMock.

    ft.controls.context.context.page is a read-only property that raises
    RuntimeError outside a running Flet app.  Patching it at the class
    level with a PropertyMock avoids triggering the original getter.
    Returns (mock_page, cleanup_fn).
    """
    mock_page = mock.MagicMock()
    mock_page.on_keyboard_event = None

    p = mock.patch.object(
        type(_flet_ctx.context),
        "page",
        mock.PropertyMock(return_value=mock_page),
    )
    p.start()
    return mock_page, p.stop


def test_handler_dispatches_ctrl_k_to_on_search():
    mock_page, cleanup = _mock_context_page()
    try:
        on_search = mock.MagicMock()

        with mock.patch("flet.on_mounted") as mock_mounted:
            use_keyboard_shortcuts(
                controller=mock.MagicMock(),
                on_search=on_search,
            )
            assert mock_mounted.called
            installer = mock_mounted.call_args[0][0]
            installer()

        handler = mock_page.on_keyboard_event
        assert handler is not None

        async def _run():
            fake_event = mock.Mock()
            fake_event.ctrl = True
            fake_event.key = "k"
            await handler(fake_event)

        asyncio.run(_run())
        on_search.assert_called_once()
    finally:
        cleanup()


def test_handler_chains_to_previous_handler_for_unhandled_keys():
    mock_page, cleanup = _mock_context_page()
    try:
        previous_handler = mock.MagicMock()
        mock_page.on_keyboard_event = previous_handler

        with mock.patch("flet.on_mounted") as mock_mounted:
            use_keyboard_shortcuts(controller=mock.MagicMock())
            installer = mock_mounted.call_args[0][0]
            installer()

        handler = mock_page.on_keyboard_event
        assert handler is not None

        async def _run():
            fake_event = mock.Mock()
            fake_event.ctrl = False
            fake_event.key = "a"
            await handler(fake_event)

        asyncio.run(_run())
        previous_handler.assert_called_once()
    finally:
        cleanup()


def test_handler_does_not_swallow_arrow_keys():
    """Arrow keys are navigation — they must not be intercepted."""
    mock_page, cleanup = _mock_context_page()
    try:
        with mock.patch("flet.on_mounted") as mock_mounted:
            use_keyboard_shortcuts(controller=mock.MagicMock())
            installer = mock_mounted.call_args[0][0]
            installer()

        handler = mock_page.on_keyboard_event
        assert handler is not None

        async def _run():
            fake_event = mock.Mock()
            fake_event.ctrl = False
            fake_event.key = "ArrowDown"
            await handler(fake_event)

        # No crash — arrow keys pass through (with no-op previous handler)
        asyncio.run(_run())
    finally:
        cleanup()


def test_on_search_coroutine_is_awaited():
    """on_search coroutine must be awaited (not fire-and-forget),
    so that the search tab switch happens before subsequent keys."""
    mock_page, cleanup = _mock_context_page()
    try:
        order: list[str] = []

        async def on_search() -> None:
            order.append("search")

        with mock.patch("flet.on_mounted") as mock_mounted:
            use_keyboard_shortcuts(controller=mock.MagicMock(), on_search=on_search)
            installer = mock_mounted.call_args[0][0]
            installer()

        handler = mock_page.on_keyboard_event

        async def _run():
            fake_event = mock.Mock()
            fake_event.ctrl = True
            fake_event.key = "k"
            await handler(fake_event)

        asyncio.run(_run())
        assert order == ["search"]
    finally:
        cleanup()


def test_installer_returns_cleanup_that_restores_previous_handler():
    """The installer returns a cleanup callable that, when invoked,
    restores the original page.on_keyboard_event — preventing handler
    nesting across remounts."""
    mock_page, cleanup = _mock_context_page()
    try:
        original = mock.MagicMock()
        mock_page.on_keyboard_event = original

        with mock.patch("flet.on_mounted") as mock_mounted:
            use_keyboard_shortcuts(controller=mock.MagicMock())
            installer = mock_mounted.call_args[0][0]
            clean = installer()

        # After install, handler is our _handler (not the original)
        assert mock_page.on_keyboard_event is not original
        assert callable(mock_page.on_keyboard_event)

        # After cleanup, the original handler is restored
        clean()
        assert mock_page.on_keyboard_event is original
    finally:
        cleanup()


def test_cleanup_on_remount_prevents_handler_nesting():
    """Simulate mount → unmount (cleanup) → remount to verify the
    closure chain does not grow beyond one level."""
    mock_page, cleanup = _mock_context_page()
    try:
        original = mock.MagicMock()
        mock_page.on_keyboard_event = original

        with mock.patch("flet.on_mounted") as mock_mounted:
            use_keyboard_shortcuts(controller=mock.MagicMock())
            installer = mock_mounted.call_args[0][0]
            clean1 = installer()

        handler1 = mock_page.on_keyboard_event
        assert handler1 is not original

        # Unmount
        clean1()
        assert mock_page.on_keyboard_event is original

        # Remount
        with mock.patch("flet.on_mounted") as mock_mounted:
            use_keyboard_shortcuts(controller=mock.MagicMock())
            installer = mock_mounted.call_args[0][0]
            clean2 = installer()

        handler2 = mock_page.on_keyboard_event
        assert handler1 is not handler2

        # handler1 and handler2 are different closures because each
        # _install creates a fresh one — but they both chain to the
        # same 'previous' (original).  Verify no deep nesting by
        # checking that handler2's chained call reaches original.
        async def _run():
            fake_event = mock.Mock()
            fake_event.ctrl = False
            fake_event.key = "a"
            await handler2(fake_event)

        asyncio.run(_run())
        # original should be called exactly once (handler2 -> original)
        # NOT twice (handler2 -> handler1 -> original)
        original.assert_called_once()

        # Clean up second mount
        clean2()
        assert mock_page.on_keyboard_event is original
    finally:
        cleanup()
