"""use_keyboard_shortcuts — wire desktop keyboard shortcuts via the
page-level KeyboardEvent (which carries shift/ctrl/alt/meta flags).

Flet's KeyboardListener (used by use_focus_scope) only exposes e.key
with no modifier flags. For desktop shortcuts that need Ctrl+K, Ctrl+R,
etc., we must use page.on_keyboard_event instead.

Because page.on_keyboard_event is a single-slot event, this hook saves
the previous handler and chains to it after handling the shortcut. This
mirrors the pattern used by the former ImmersivePlayer.did_mount swap,
but properly uninstalled on unmount.

Usage in AppShell (dashboard branch):

    from hooks.use_keyboard_shortcuts import use_keyboard_shortcuts

    controller = ft.use_context(ControllerMethodsCtx)
    use_keyboard_shortcuts(
        controller=controller,
        on_search=lambda: _set_tab(2),   # switch to search tab
        on_refresh=controller.refresh_channels,
    )
"""

from collections.abc import Awaitable, Callable
from typing import Any

import flet as ft


def use_keyboard_shortcuts(
    controller: Any,
    *,
    on_search: Callable[[], Awaitable[None]] | None = None,
    on_refresh: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """Install a page-level keyboard shortcut handler on mount.

    Registered with ft.on_mounted so it runs once when the AppShell
    component first renders. The handler chains to any existing
    page.on_keyboard_event so it does not swallow unhandled keys.

    On unmount the previous page.on_keyboard_event handler is restored,
    preventing handler nesting when the component remounts.

    Args:
        controller: ControllerMethods instance (read via use_context).
        on_search: called when Ctrl+K is pressed.
        on_refresh: called when Ctrl+R is pressed.
    """

    def _install() -> Callable[[], None]:
        """Install the keyboard shortcut handler and return a cleanup
        that restores the previous handler on unmount.

        Because this function is synchronous (not async), the flet
        effect scheduler captures its return value as the effect's
        cleanup, which runs automatically when the component unmounts.
        """
        from flet import context as _ctx

        try:
            page = _ctx.page
        except Exception:
            return lambda: None

        previous = page.on_keyboard_event

        async def _handler(e: ft.KeyboardEvent) -> None:
            handled = False
            if e.ctrl and e.key.lower() == "k":
                if on_search is not None:
                    result = on_search()
                    if hasattr(result, "__await__"):
                        await result
                    handled = True
            elif e.ctrl and e.key.lower() == "r" and on_refresh is not None:
                result = on_refresh()
                if hasattr(result, "__await__"):
                    await result
                handled = True
            if not handled and previous is not None:
                result = previous(e)
                if hasattr(result, "__await__"):
                    await result

        page.on_keyboard_event = _handler

        # Returned cleanup restores the original handler on unmount,
        # preventing closure-chain nesting across remounts.
        def _cleanup() -> None:
            page.on_keyboard_event = previous

        return _cleanup

    ft.on_mounted(_install)
