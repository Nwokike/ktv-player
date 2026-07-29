"""FocusScope — declarative back-key capture for TV-remote + desktop Esc.

Replaces the legacy `core/focus_manager.py` pattern (a module-level counter
+ stateful manager object). Spatial D-pad traversal is delegated entirely
to Flutter's DirectionalFocusTraversalPolicy. The scope only catches
Back/Escape so a parent screen can pop the view stack or trigger app back;
control auto-focus is left to controls that natively support `autofocus`
(e.g. `TextField`, `Checkbox`), not to `Container`.

This is NOT a @ft.component — it uses no hooks and is a pure composition
of existing controls, so calling it outside a render frame is valid and
testable without a Renderer context.

Verified API (Flet 0.86.4, .venv/lib/python3.14/site-packages/flet/):
- ft.KeyboardListener(content=..., on_key_down=...) wraps any Control.
- KeyDownEvent has `.key: str` (no modifier flags — not needed here).
- The legacy code used page.on_keyboard_event(KeyboardEvent) which accepts
  additional modifier fields; KeyboardListener's KeyDownEvent is leaner.
"""

from collections.abc import Awaitable, Callable

import flet as ft
from flet.controls.control import Control

# Keys the Material platform emits for system Back. Verified against legacy
# `core/focus_manager.py` line 31 (same set kept for parity).
_BACK_KEYS = frozenset({"Back", "Escape", "BrowserBack", "Go Back"})


def FocusScope(
    child: Control,
    on_back: Callable[..., Awaitable[None] | None] | None = None,
) -> Control:
    """Wrap child in a KeyboardListener that fires `on_back` on Back/Escape.

    Args:
        child: the control tree to mount under the scope.
        on_back: optional async-or-sync callback receiving the KeyDownEvent.
            If omitted, Back/Escape just propagate (which on Flutter/Material
            translates to the system back action).
    """

    async def handle_key_down(e) -> None:
        if e.key in _BACK_KEYS and on_back is not None:
            result = on_back(e)
            if hasattr(result, "__await__"):
                await result

    return ft.KeyboardListener(
        on_key_down=handle_key_down,
        content=child,
        expand=True,
    )
