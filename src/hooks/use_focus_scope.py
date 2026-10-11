"""focus_scope — declarative back-key capture for TV-remote + desktop Esc."""

import logging
from collections.abc import Awaitable, Callable

import flet as ft
from flet import Control

logger = logging.getLogger(__name__)

# Keys the Material platform emits for system Back. "Go Back" was dropped:
# it is not a standard KeyboardEvent.key value (verified against the key set
# observed on device + desktop Esc path) and its only justification was a
# legacy file that no longer exists.
_BACK_KEYS = frozenset({"Back", "Escape", "BrowserBack"})


def focus_scope(
    child: Control,
    on_back: Callable[[ft.KeyDownEvent], Awaitable[None] | None] | None = None,
) -> Control:
    """Wrap child in a KeyboardListener that fires `on_back` on Back/Escape.

    NOTE: this is a back-key interceptor, not a focus-trapping scope — D-pad
    traversal and focus cycling stay with Flutter's native focus system. The
    name is historical; FocusScope below is a compat alias.

    The listener takes autofocus so Back/Escape delivery doesn't depend on
    whichever button happens to hold focus (without it, an unfocused player
    overlay swallows the first Back press). Cross-reference: the page-level
    handler in use_keyboard_shortcuts explicitly skips /play routes so the
    two layers never double-close the player.

    Args:
        child: the control tree to mount under the scope.
        on_back: optional async-or-sync callback receiving the KeyDownEvent.
            If omitted, Back/Escape just propagate (which on Flutter/Material
            translates to the system back action).
    """
    handling = {"value": False}

    async def handle_key_down(e: ft.KeyDownEvent) -> None:
        if e.key not in _BACK_KEYS or on_back is None:
            return
        if handling["value"]:
            return
        handling["value"] = True
        try:
            result = on_back(e)
            if hasattr(result, "__await__"):
                await result
        except Exception:
            logger.exception("FocusScope on_back failed for key %r", e.key)
        finally:
            handling["value"] = False

    # The expanding Container is load-bearing, not decoration: Flet's
    # KeyboardListener extends Control, not LayoutControl, so it has no
    # layout behaviour of its own. An `expand=True` on it is accepted and
    # then ignored, and a listener mounted straight onto a View (as the
    # player is) gives the Stack underneath it no bounds at all — the
    # decoder keeps playing audio while the texture has no area, which is
    # the white player with sound. Verified against
    # .venv/Lib/site-packages/flet/controls/core/keyboard_listener.py.
    return ft.Container(
        content=ft.KeyboardListener(
            content=child,
            autofocus=True,
            on_key_down=handle_key_down,
        ),
        expand=True,
    )


# Compat alias: existing callers + tests import FocusScope.
FocusScope = focus_scope
