"""use_keyboard_shortcuts — wire desktop keyboard shortcuts via the
page-level KeyboardEvent (which carries shift/ctrl/alt/meta flags).

Flet's KeyboardListener (used by focus_scope) only exposes e.key
with no modifier flags. For desktop shortcuts that need Ctrl+K, Ctrl+R,
etc., we must use page.on_keyboard_event instead.

Because page.on_keyboard_event is a single-slot event, this hook saves
the previous handler and chains to it after handling the shortcut.

Callbacks must be STABLE references: the installer runs once on mount
(ft.on_mounted has no deps array), so a re-render with new lambdas would
leave the installed handler calling the first-render closures. AppShell
passes the stable controller + module-level lambdas — keep it that way.

Usage in AppShell (dashboard branch):

    from hooks.use_keyboard_shortcuts import use_keyboard_shortcuts

    controller = ft.use_context(ControllerMethodsCtx)
    use_keyboard_shortcuts(
        controller=controller,
        on_search=lambda: set_search_mode("tv"),
        on_refresh=controller.refresh_channels,
    )
"""

import logging
from collections.abc import Callable
from typing import Any

import flet as ft

logger = logging.getLogger(__name__)


def use_keyboard_shortcuts(
    controller: Any,
    *,
    on_search: Callable[[], Any] | None = None,
    on_refresh: Callable[[], Any] | None = None,
) -> None:
    """Install a page-level keyboard shortcut handler on mount.

    Registered with ft.on_mounted so it runs once when the AppShell
    component first renders. The handler chains to any existing
    page.on_keyboard_event so it does not swallow unhandled keys.

    On unmount the previous page.on_keyboard_event handler is restored
    (identity-guarded: only when ours is still installed, so unmounting
    never clobbers a newer handler installed after us), preventing handler
    nesting when the component remounts.

    Args:
        controller: ControllerMethods instance (read via use_context).
        on_search: called when Ctrl+K / Cmd+K is pressed.
        on_refresh: called when Ctrl+R / Cmd+R is pressed.
    """

    def _install() -> Callable[[], None]:
        """Install the keyboard shortcut handler and return a cleanup
        that restores the previous handler on unmount.

        Because this function is synchronous (not async), the flet
        effect scheduler captures its return value as the effect's
        cleanup, which runs automatically when the component unmounts.
        (Never convert _install to async: the coroutine's return would be
        lost inside the scheduled task and never become cleanup.)
        """
        from flet import context as _ctx

        try:
            page = _ctx.page
        except RuntimeError:
            logger.debug("Shortcuts: no page bound at install", exc_info=True)
            return lambda: None

        previous = page.on_keyboard_event

        async def _handler(e: ft.KeyboardEvent) -> None:
            handled = False
            key = e.key or ""
            mod = e.ctrl or e.meta
            if key == "Escape" and not (e.ctrl or e.meta or e.shift or e.alt):
                # Esc is the desktop/TV equivalent of the Android back
                # press. While a player view is open the player's own focus
                # scope already handles it — closing it from here as well
                # would save and pop the view twice, landing the user on the
                # bare /blank underlay. (Cross-ref: hooks/use_focus_scope.)
                player_open = any(
                    getattr(v, "route", "") == "/play" for v in (page.views or [])
                )
                pop_views = getattr(controller, "pop_views", None)
                if not player_open and callable(pop_views):
                    result = pop_views()
                    if hasattr(result, "__await__"):
                        await result
                    handled = True
            elif mod and key.lower() == "k":
                if on_search is not None:
                    result = on_search()
                    if hasattr(result, "__await__"):
                        await result
                    handled = True
            elif mod and key.lower() == "r" and on_refresh is not None:
                result = on_refresh()
                if hasattr(result, "__await__"):
                    await result
                handled = True
            if not handled and previous is not None:
                result = previous(e)
                if hasattr(result, "__await__"):
                    await result

        page.on_keyboard_event = _handler

        # Returned cleanup restores the original handler on unmount —
        # identity-guarded so interleaved mount/unmount of two chainers
        # never wipes the newer handler.
        def _cleanup() -> None:
            if page.on_keyboard_event is _handler:
                page.on_keyboard_event = previous

        return _cleanup

    ft.on_mounted(_install)
