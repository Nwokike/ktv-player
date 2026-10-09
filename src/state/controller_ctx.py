"""Context exposing AppController callbacks to the component tree.

`AppShell` is rendered inside the `page.render()` callback holding a single
`ContextProvider` with a `ControllerMethods` dataclass (see src/main.py).
Components read callbacks via `ft.use_context(ControllerMethodsCtx)`.

Defaults are async no-ops so the shell renders safely even before the
provider is mounted (e.g. inside unit tests that instantiate AppShell
directly without a real AppController).

Mutation contract: AppShell ASSIGNS into the provided instance
(`controller.go_home = ...`). That is intentional and required —
AppController hands its own object to the provider AND reads the same
attributes off it (`self._controller_methods`), so a `dataclasses.replace`
copy left the controller holding the no-op defaults. When no provider is
mounted, `use_context` returns the shared module-level `ControllerMethods()`
default; tests that render AppShell that way would mutate it, so reset
between tests where that matters (production always mounts the provider).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import flet as ft


async def _noop_async_refresh(*_args, **_kwargs) -> None:
    """No-op async default for refresh_channels (tolerates force=True)."""


async def _noop_async_play(*_args, **_kwargs) -> None:
    """No-op async default for play_stream(url, title, ...)."""


def _noop_sync_pop_views() -> None:
    """No-op sync default for pop_views."""
    return


async def _noop_async_modal(_name: str = "") -> None:
    """No-op async default for push_modal(name)."""


async def _noop_async_pop_modal(_name: str = "") -> None:
    """No-op async default for pop_modal(name)."""


async def _noop_async_close_modal() -> None:
    """No-op async default for close_modal()."""


async def _noop_async_update_check(*_args, **_kwargs) -> None:
    """No-op async default for check_for_updates(notify_if_latest)."""


def _noop_sync_version_dialog() -> None:
    """No-op sync default for open_version_dialog()."""


def _noop_sync_open_search(_mode: str = "tv") -> None:
    """No-op sync default for open_search(mode)."""


def _noop_sync_on_non_home_tab() -> bool:
    """No-op sync default for on_non_home_tab()."""
    return False


@dataclass
class ControllerMethods:
    """Subset of AppController methods exposed to the component tree.

    Mutable (not frozen) so AppController can build it incrementally. All
    defaults are real no-ops whose signatures match the AppController
    methods — important because use_context(ControllerMethodsCtx) returns
    this exact dataclass and components await the callables directly.

    Variadic `...` slots mirror methods with optional kwargs (force, referer,
    headers, ...): the default path must never TypeError.
    """

    refresh_channels: Callable[..., Awaitable[None]] = _noop_async_refresh
    play_stream: Callable[..., Awaitable[None]] = _noop_async_play
    pop_views: Callable[[], None] = _noop_sync_pop_views
    push_modal: Callable[[str], Awaitable[None]] = _noop_async_modal
    pop_modal: Callable[[str], Awaitable[None]] = _noop_async_pop_modal
    close_modal: Callable[[], Awaitable[None]] = _noop_async_close_modal
    open_search: Callable[[str], None] = _noop_sync_open_search
    go_home: Callable[[], None] = _noop_sync_pop_views
    # True when the shell shows anything other than the Home tab. AppShell
    # installs this on every render; AppController reads it to decide
    # whether a back press returns Home or exits.
    on_non_home_tab: Callable[[], bool] = _noop_sync_on_non_home_tab
    check_for_updates: Callable[..., Awaitable[None]] = _noop_async_update_check
    open_version_dialog: Callable[[], None] = _noop_sync_version_dialog


ControllerMethodsCtx: ft.ContextProvider[ControllerMethods] = ft.create_context(
    ControllerMethods()
)

__all__ = ["ControllerMethods", "ControllerMethodsCtx"]
