"""FocusScope — declarative back-key capture for TV-remote + desktop Esc."""

from collections.abc import Awaitable, Callable

import flet as ft
from flet import Control

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

    return ft.Container(
        content=ft.KeyboardListener(
            on_key_down=handle_key_down,
            content=child,
        ),
        expand=True,
    )
