"""Context exposing AppController callbacks to the component tree.

`AppShell` is rendered via `page.render(AppShell)` with no positional args
(see src/main.py), so AppController cannot pass callbacks into AppShell's
constructor. Instead, AppController mounts a single `ContextProvider`
holding a `ControllerMethods` dataclass before calling page.render().
Components read callbacks via `ft.use_context(ControllerMethodsCtx)`.

Defaults are async no-ops so the shell renders safely even before the
provider is mounted (e.g. inside unit tests that instantiate AppShell
directly without a real AppController).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import flet as ft


async def _noop_async() -> None:
    """No-op async default for refresh_channels (no IO, returns immediately)."""


async def _noop_async2(_a: str, _b: "str | None" = None) -> None:
    """No-op async default for play_stream(url, title)."""


def _noop_sync() -> None:
    """No-op sync default for pop_views."""
    return


@dataclass
class ControllerMethods:
    """Subset of AppController methods exposed to the component tree.

    Mutable (not frozen) so AppController can build it incrementally. All
    defaults are real no-ops whose signatures match the AppController
    methods — important because use_context(ControllerMethodsCtx) returns
    this exact dataclass and components await the callables directly.
    """

    refresh_channels: Callable[[], Awaitable[None]] = _noop_async
    play_stream: Callable[[str, "str | None"], Awaitable[None]] = _noop_async2
    pop_views: Callable[[], None] = _noop_sync


ControllerMethodsCtx = ft.create_context(ControllerMethods())

__all__ = ["ControllerMethods", "ControllerMethodsCtx"]
