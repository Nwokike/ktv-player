# Milestone 1 — Frontend Rewrite Scaffold (AppShell + Onboarding) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Note from the user: the main agent must verify every code change before commit — run tests, read diffs. No subagent-only edits.**

**Goal:** Set up the new `src/app_next/` frontend tree, gate it behind a `KTV_FRONTEND` env flag in `AppController`, mount the `AppShell` component via `page.render(AppShell)`, and reimplement the Onboarding screen as a `@ft.component` with hooks. After this milestone the app runs (legacy-by-default); running `KTV_FRONTEND=next flet run src/main.py` shows the new Onboarding flow on first launch (online + offline states), and existing tests are green.

**Architecture:** Adds a parallel frontend in `src/app_next/` without touching legacy `src/views/`. The single entry-point change is a 3-line env-flag branch in `AppController.init()` that either calls the legacy bootstrap (today's behavior) or `page.render(AppShell)`. `AppShell` is a `@ft.component` that subscribes to `@ft.observable` global state via `create_context`, decides between Onboarding and the dashboard scaffold (mostly placeholders in M1 — full screens come in M2–M4), and wires D-pad Back navigation through a tiny declarative `FocusScope` component (no global counter). The onboarding screen uses `use_state`/`use_effect`/`use_storage` and on submit writes the same `accepted_terms=true` key `AppController.init` reads, so observable `state.has_accepted_terms` flips and the shell re-renders to the scaffold without `page.update()`. Deep-link and player view push are left untouched — `AppController.play_stream` still pushes a classical `ft.View`.

**Tech Stack:** Flet 0.86.3 (hooks + `@ft.component` + `@ft.observable` + `create_context`); pytest; existing `database.manager` JSON persistence; existing `channels.provider.ChannelProvider` for country list; existing `core.theme.AppTheme` / `AppColors` / `core.tokens` design tokens.

**Reference docs:**
- Design spec: `docs/superpowers/specs/2026-07-28-frontend-rewrite-design.md`
- API facts verified against `.venv/lib/python3.13/site-packages/flet/` (cited inline per task).

---

## File structure for this milestone

| Path | Action | Responsibility (one each) |
|---|---|---|
| `src/app_next/__init__.py` | Create | Package marker. |
| `src/app_next/state/__init__.py` | Create | Package marker. |
| `src/app_next/state/app_state.py` | Create | `AppStateCtx = create_context(...)` re-exporting the existing `core.state.state` observable singleton. M1 adds no new state — pure adapter so M2+ components only import from `app_next`. |
| `src/app_next/state/controller_ctx.py` | Create | `ControllerMethods` dataclass + `ControllerMethodsCtx` context exposing `AppController` callbacks (refresh_channels, play_stream, pop_views, …) to the component tree. Defaults are no-op so the shell renders safely when no provider is mounted (unit tests). M1 wires all three from `AppController.init`; later milestones extend the dataclass. |
| `src/app_next/hooks/__init__.py` | Create | Package marker. |
| `src/app_next/hooks/use_storage.py` | Create | Tiny async facade over `database.manager.db_manager`. Exposes the subset the onboarding screen needs in M1: `set_setting`, `get_setting`. |
| `src/app_next/hooks/use_focus_scope.py` | Create | Declarative `@ft.component` `FocusScope(child, autofocus_root, on_back)`. Wraps `child` in a `KeyboardListener` to capture Back/Escape; relies on Flutter's `DirectionalFocusTraversalPolicy` for spatial traversal. Replaces `core/focus_manager.py`'s global counter pattern — but does NOT delete `core/focus_manager.py` in M1 (deletion is at cutover, M6). |
| `src/app_next/components/__init__.py` | Create | Package marker. |
| `src/app_next/components/loading_state.py` | Create | `LoadingState` component — centered `ProgressRing` with the given label. One-liner, used by onboarding offline retry & by later screens. |
| `src/app_next/components/offline_flow.py` | Create | `OfflineFlow(on_retry, on_skip)` component — used by onboarding when the channel fetch fails. |
| `src/app_next/screens/__init__.py` | Create | Package marker. |
| `src/app_next/screens/onboarding_screen.py` | Create | `@ft.component OnboardingScreen(countries, on_complete)`. Owns `selected_country, terms_accepted, is_loading, is_offline` as `use_state`. Online form: logo, country picker (virtualized `ListView`), terms checkbox, submit button. Offline: `OfflineFlow`. Connectivity probe runs in `on_mounted`. |
| `src/app_next/screens/placeholder_screen.py` | Create | `@ft.component PlaceholderScreen(name)` — a transparent placeholder for Home/Search/Local/Settings in M1 (full versions come M2–M4). |
| `src/app_next/app_shell.py` | Create | `@ft.component AppShell()`. Reads `AppStateCtx`. If `state.is_first_launch or not state.has_accepted_terms` → render `FocusScope(OnboardingScreen(...))`; else render a `Scaffold`-style `Column` with a `PlaceholderScreen(tab_name)` body and a `NavigationBar` of 4 destinations. Wires Back/Escape to `page.pop_views_until` via `use_view_path`. |
| `src/app_next/__init__.py` (re-edit) | Modify | Export `AppShell` so `AppController` imports `from app_next import AppShell`. |
| `src/main.py` | Modify | Three-line branch in `AppController.init()`: after services restored, if `KTV_FRONTEND == "next"` call `page.render(AppShell)` instead of starting legacy routing. Legacy path unchanged. |
| `tests/app_next/__init__.py` | Create | Package marker. |
| `tests/app_next/test_use_storage.py` | Create | Tests for the storage facade. |
| `tests/app_next/test_app_state_context.py` | Create | Tests that `AppStateCtx` resolves to the singleton `core.state.state` and that toggling `state.has_accepted_terms` reflects through a subscribed mock component. |
| `tests/app_next/test_focus_scope.py` | Create | Smoke test: `FocusScope` mounts without raising, captures `on_back` only on Back/Escape keys, lets other keys pass. |
| `tests/app_next/test_onboarding_screen.py` | Create | Behavior tests for `OnboardingScreen` submit logic: (a) submit disabled unless terms+country selected, (b) submit fires `on_complete` once with the right persistence calls, (c) offline retry re-runs probe, (d) offline skip-`"Other"` runs `on_complete`. |
| `tests/app_next/test_app_shell.py` | Create | Smoke + branch test: `AppShell` renders OnboardingScreen when first-launch; renders placeholder+nav when terms accepted. |
| `tests/app_next/test_env_toggle.py` | Create | Tests the env-flag branch in `AppController.init` by monkey-patching `os.environ` + a fake `ft.Page` (we instantiate the legacy `AppController` and assert it calls `page.render` only when env == "next"). |
| `tests/app_next/conftest.py` | Create | Shared fixtures: a `fake_page()` providing minimal `ft.Page`-like protocols `page.render`, `page.show_dialog`, `page.update`, `page.push_route`, etc. — enough for component smoke renders. |

**Files NOT touched in M1** (to keep blast radius small):
- `src/views/*` (legacy onboarding stays, used when env=legacy)
- `src/core/state.py` (favorites bug fix is M5)
- `src/core/focus_manager.py` (kept; deleted at M6)
- `src/components/player/*` (untouched, all milestones)
- `src/services/*`, `src/database/*`, `src/channels/*` (untouched, all milestones)

---

## Task 1: Add env-flag shim to `AppController.init` and unit-test it

**Files:**
- Modify: `src/main.py:38-48` (after `init()` begins; before services restored) and `src/main.py:288-296` (`main()` target — defer route_change registration if next, because shell does its own routing)
- Create: `tests/app_next/__init__.py`
- Create: `tests/app_next/conftest.py`
- Create: `tests/app_next/test_env_toggle.py`

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/__init__.py`:

```python
```

Create `tests/app_next/conftest.py`:

```python
"""Shared fixtures for app_next tests."""

from collections import deque
from typing import Any

import pytest


class FakePage:
    """Minimal stand-in for ft.Page for unit testing the controller branch.

    Only the methods AppController touches are implemented. Component
    render tests in later tasks extend this with `components_mode` toggling.
    """

    def __init__(self, route: str = "/"):
        self.title = ""
        self.padding: Any = 0
        self.spacing = 0
        self.fonts: dict[str, str] = {}
        self.theme = None
        self.dark_theme = None
        self.theme_mode = None
        self.route = route
        self.views: list[Any] = []
        self.on_error = None
        self.on_route_change = None
        self.on_view_pop = None
        self._render_calls: deque = deque()
        self._update_calls: int = 0
        self._dialogs: deque = deque()
        self._pushed_routes: deque = deque()
        # protocols.Album controls support `page.services.append(...)` for FilePicker etc.
        self.services: list[Any] = []

    def render(self, component: Any, *args: Any, **kwargs: Any) -> None:
        self._render_calls.append((component, args, kwargs))

    def render_views(self, component: Any, *args: Any, **kwargs: Any) -> None:
        self._render_calls.append((component, args, kwargs))

    def update(self, *controls: Any) -> None:
        self._update_calls += 1

    def schedule_update(self) -> None:
        self._update_calls += 1

    def show_dialog(self, dialog: Any) -> None:
        self._dialogs.append(dialog)

    def push_route(self, route: str) -> None:
        self._pushed_routes.append(route)

    def pop_views_until(self, route: str, result: Any = None) -> None:
        while self.views and getattr(self.views[-1], "route", None) != route:
            self.views.pop()

    def run_task(self, coro_or_fn, *args, **kwargs):
        # In tests we don't run a real loop; record the call.
        self._render_calls.append(("run_task", coro_or_fn, args, kwargs))

    @property
    def render_calls(self):
        return list(self._render_calls)

    @property
    def pushed_routes(self):
        return list(self._pushed_routes)


@pytest.fixture
def fake_page():
    return FakePage()
```

Create `tests/app_next/test_env_toggle.py`:

```python
"""Tests for the KTV_FRONTEND=next env flag in AppController.init."""

import os
from unittest import mock

import flet as ft

import pytest

from src.main import AppController


def _make_controller(fake_page):
    """Build an AppController without calling init()."""
    return AppController(fake_page)


async def test_init_renders_shell_when_env_next(fake_page, monkeypatch):
    """When KTV_FRONTEND=next, init() ends with page.render(AppShell)."""
    monkeypatch.setenv("KTV_FRONTEND", "next")
    controller = _make_controller(fake_page)

    # Stub every async service call init() makes — we only care about the
    # render branch at the bottom.
    async def _noop(*a, **k):
        return None

    with (
        mock.patch("src.main.db_manager") as dbm,
        mock.patch("src.main.AdService") as ads,
        mock.patch("src.main.LivelinessChecker") as lchk,
        mock.patch("src.main.FocusManager") as fmgr,
        mock.patch("src.main.AppController.load_channels", _noop),
    ):
        dbm.init_db = _noop
        dbm.get_setting = _noop
        dbm.get_favorite_urls = _noop
        dbm.get_history = _noop
        dbm.load_liveliness_cache = _noop
        ads.return_value.gather_consent = _noop
        ads.return_value.preload_interstitial = _noop

        # We do NOT want the legacy route_change to run (it would try to
        # import legacy views). main() runs it after init; we skip main()
        # and call init() directly.
        await controller.init()

    # init() should have called page.render exactly once with AppShell.
    assert len(fake_page.render_calls) == 1
    rendered_component = fake_page.render_calls[0][0]
    # AppShell is the imported class
    from app_next import AppShell

    assert rendered_component is AppShell


async def test_init_does_not_render_shell_when_env_legacy(fake_page, monkeypatch):
    """When KTV_FRONTEND is unset or 'legacy', init() never calls page.render()."""
    monkeypatch.delenv("KTV_FRONTEND", raising=False)
    controller = _make_controller(fake_page)

    async def _noop(*a, **k):
        return None

    with (
        mock.patch("src.main.db_manager") as dbm,
        mock.patch("src.main.AdService") as ads,
        mock.patch("src.main.LivelinessChecker") as lchk,
        mock.patch("src.main.FocusManager") as fmgr,
    ):
        dbm.init_db = _noop
        dbm.get_setting = _noop
        dbm.get_favorite_urls = _noop
        dbm.get_history = _noop
        dbm.load_liveliness_cache = _noop
        ads.return_value.gather_consent = _noop
        ads.return_value.preload_interstitial = _noop

        await controller.init()

    assert fake_page.render_calls == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_env_toggle.py -v
```

Expected: ImportError — `ModuleNotFoundError: No module named 'app_next'` and/or no render call assertion failure. Both confirm the test runs and the code-under-test is absent.

- [ ] **Step 3: Implement the env-flag branch (minimal)**

Create `src/app_next/__init__.py`:

```python
"""New Flet-component-based frontend for KTV Player.

Gated behind KTV_FRONTEND=next until cutover. See
docs/superpowers/specs/2026-07-28-frontend-rewrite-design.md.
"""
```

(The `AppShell` export is added in Task 9 once `app_shell.py` exists.)

Modify `src/main.py` line 30 area — wrap the AppController class. Add `import os` (already present at top — confirmed line 6) and a backend-flag constant near the imports (line ~26). Then modify `init()` to branch at the end. The legacy bootstrap remains the default.

Edit `src/main.py` (insert a new constant below `logger = logging.getLogger(__name__)` on line 26):

```python
logger = logging.getLogger(__name__)


# Toggle between legacy (`page.views.append(ft.View(...))`) bootstrap and the
# new `page.render(AppShell)` component-based frontend. Set via env var so
# testers/devs can A/B without code changes. Default: legacy (zero behavior
# change during the rewrite).
def _frontend_is_next() -> bool:
    return os.environ.get("KTV_FRONTEND", "legacy") == "next"
```

Edit `src/main.py` `init()` — add at the very end (after line 91 `self.focus_manager.set_back_handler(...)`):

```python
        # Focus manager
        self.focus_manager = FocusManager(self.page)
        self.focus_manager.set_back_handler(self._handle_back)

        # Frontend mount point. When KTV_FRONTEND=next, hand the page over to
        # the new component tree; AppShell owns routing, theme syncing, and
        # the NavigationBar. The legacy code path below is untouched.
        if _frontend_is_next():
            from app_next import AppShell

            self.page.render(AppShell)
            return
```

Leave everything else in `init()` above intact. The legacy `route_change` registered in `main()` will still run when env=legacy; when env=next it does nothing harmful because `AppShell` re-renders the dashboard itself (Task 9). To be safe, `main()` is also updated (next step).

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/app_next/test_env_toggle.py -v
```

Expected: 2 passed. Note: the next-branch test asserts `rendered_component is AppShell`; that requires `AppShell` to be importable — but we haven't written `app_shell.py` yet. So this test is expected to STILL fail with `ImportError: cannot import name 'AppShell' from 'app_next'` until Task 9. That's fine — TDD rhythm: red → commit minimal scaffold → green at Task 9.

To get the **legacy** test green now (proving we haven't broken the default path), we can let this task's commit contain just the controller branch + the legacy test passing; the next-branch test is marked `pytest.mark.xfail` until Task 9, after which we un-xfail it.

Amend `tests/app_next/test_env_toggle.py`:

```python
import pytest


@pytest.mark.xfail(reason="AppShell lands in Task 9")
async def test_init_renders_shell_when_env_next(fake_page, monkeypatch):
```

(Keep the rest of the body identical.)

- [ ] **Step 5: Verify legacy tests still green**

Run:

```bash
uv run pytest -q
```

Expected: full suite green except the single xfail. Pre-existing `tests/test_state.py`, `tests/test_url_validator.py`, etc. must pass unchanged.

Run the linter:

```bash
uv run ruff check src/main.py tests/app_next/
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/main.py src/app_next/__init__.py tests/app_next/__init__.py tests/app_next/conftest.py tests/app_next/test_env_toggle.py
git commit -m "feat(app_next): scaffold package and KTV_FRONTEND=next env-flag branch

Adds the env-flag branch at the bottom of AppController.init. When
KTV_FRONTEND=next, page.render(AppShell) is invoked (AppShell itself
lands in a later task; the next-branch test is xfail until then).
Legacy path is untouched — full pytest suite stays green."
```

---

## Task 2: `AppStateCtx` adapter — expose the existing observable singleton via `create_context`

**Files:**
- Create: `src/app_next/state/__init__.py`
- Create: `src/app_next/state/app_state.py`
- Create: `tests/app_next/test_app_state_context.py`

**Why:** Every M2+ component will subscribe to global state via `use_context(AppStateCtx)`. We do NOT duplicate or fork state — just wrap the existing `core.state.state` (already `@ft.observable`) so components only ever import from `app_next`. Verified: `ft.create_context(default)` returns a `ContextProvider` whose default value is returned to consumers when no explicit `ContextProvider` ancestor is present (`flet/components/hooks/use_context.py`).

- [ ] **Step 1: Write the failing test**

Create `src/app_next/state/__init__.py`:

```python
```

Create `tests/app_next/test_app_state_context.py`:

```python
"""Tests for the AppStateCtx adapter."""

from app_next.state.app_state import AppStateCtx
from core.state import state as core_singleton


def test_app_state_context_resolves_to_core_singleton():
    """The default value of AppStateCtx is the core.state module singleton."""
    # create_context stores the default on the returned ContextProvider.
    assert AppStateCtx.default_value is core_singleton


def test_app_state_context_exposes_name_documenting_sibling():
    """Sanity: contexts have a readable repr for debugging component trees."""
    assert "AppState" in repr(AppStateCtx) or "Context" in repr(AppStateCtx)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_app_state_context.py -v
```

Expected: `ModuleNotFoundError: No module named 'app_next.state.app_state'`.

- [ ] **Step 3: Implement the adapter**

Create `src/app_next/state/app_state.py`:

```python
"""AppState context — component-facing adapter over the legacy observable state.

We do NOT duplicate state. The existing `core.state.state` is already
`@ft.observable`; this file just re-exports it through a context provider
created via `ft.create_context(default_value=state)` so that components
can subscribe via `use_context(AppStateCtx)` and re-render when any
observable field flips.

OBSERVABLE SUBSCRIPTION RULE: Components MUST access state via
`use_context(AppStateCtx)` rather than a plain `from ... import state`.
Reason: `use_context` checks `isinstance(value, Observable)` and, if True,
auto-attaches an ObservableSubscription to the calling component (verified
at .venv/lib/python3.13/site-packages/flet/components/hooks/use_context.py
lines 105-106). A plain import does NOT subscribe — so mutations to
state.has_accepted_terms or state.channels from one component would NOT
trigger re-render in other components. This auto-subscription is what makes
the AppShell's Onboarding → dashboard transition fire after the user
submits onboarding.

See design spec section D, "Global observable state".
"""

import flet as ft

from core.state import state

#: Context provider whose default value is the legacy observable singleton.
#: AppShell mounts a `ContextProvider(AppStateCtx, value=state)` near the root
#: so every descendant component can subscribe deterministically.
AppStateCtx = ft.create_context(state)

# Re-export so consumers can `from app_next.state.app_state import state`
# without reaching into `core.state` directly. Same object — single source
# of truth for persistence and observable mutation semantics.
__all__ = ["AppStateCtx", "state"]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/app_next/test_app_state_context.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check src/app_next/state/ tests/app_next/test_app_state_context.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/app_next/state/ tests/app_next/test_app_state_context.py
git commit -m "feat(app_next.state): AppStateCtx exposing legacy observable singleton

Wraps core.state.state (already @ft.observable) in ft.create_context so
M2+ components can subscribe via use_context(AppStateCtx). No state fork."
```

---

## Task 3: `use_storage` async facade — `set_setting` + `get_setting`

**Files:**
- Create: `src/app_next/hooks/__init__.py`
- Create: `src/app_next/hooks/use_storage.py`
- Create: `tests/app_next/test_use_storage.py`

**Why:** Components should never `import database.manager` directly — that pins them to a specific persistence implementation. `use_storage()` (note: NOT a hook in the React sense, just a thin callable) returns a record exposing async `set_setting(key, value)` and `get_setting(key)` delegating to `db_manager`. Future milestones add more methods; M1 only needs the two the onboarding screen uses. Verified: `database.manager.db_manager` exposes both as async methods (lines 98, 104 of `src/database/manager.py`).

- [ ] **Step 1: Write the failing test**

Create `src/app_next/hooks/__init__.py`:

```python
```

Create `tests/app_next/test_use_storage.py`:

```python
"""Tests for the use_storage async facade over database.manager.db_manager."""

from unittest import mock

import pytest

from app_next.hooks.use_storage import use_storage, Storage


async def test_use_storage_returns_a_storage_instance():
    storage = use_storage()
    assert isinstance(storage, Storage)


async def test_set_setting_delegates_to_db_manager():
    storage = use_storage()
    with mock.patch("app_next.hooks.use_storage.db_manager") as dbm:
        dbm.set_setting = mock.AsyncMock()
        await storage.set_setting("user_country", "Nigeria")
        dbm.set_setting.assert_awaited_once_with("user_country", "Nigeria")


async def test_get_setting_delegates_to_db_manager():
    storage = use_storage()
    with mock.patch("app_next.hooks.use_storage.db_manager") as dbm:
        dbm.get_setting = mock.AsyncMock(return_value="Nigeria")
        result = await storage.get_setting("user_country")
        dbm.get_setting.assert_awaited_once_with("user_country", default=None)
        assert result == "Nigeria"


async def test_get_setting_passes_default_through():
    storage = use_storage()
    with mock.patch("app_next.hooks.use_storage.db_manager") as dbm:
        dbm.get_setting = mock.AsyncMock(return_value="fallback")
        await storage.get_setting("missing", default="fallback")
        dbm.get_setting.assert_awaited_once_with("missing", default="fallback")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_use_storage.py -v
```

Expected: `ModuleNotFoundError: No module named 'app_next.hooks.use_storage'`.

- [ ] **Step 3: Implement the facade**

Create `src/app_next/hooks/use_storage.py`:

```python
"""Async storage facade for app_next components.

Wraps `database.manager.db_manager` so callers do not import the manager
directly. This is NOT a React-style hook — it's a thin factory returning
a `Storage` record. Components call `await use_storage().set_setting(...)`.

Keeping it a plain callable (not wrapped in @ft.component machinery) means
it can be used outside of component render cycles too (e.g. from utility
modules). It is named `use_storage` only to match the convention used by
the design spec; functionally it is a singleton accessor.
"""

from dataclasses import dataclass
from typing import Any

from database.manager import db_manager


@dataclass
class Storage:
    """Subset of db_manager that components need. Extend per milestone."""

    async def set_setting(self, key: str, value: str) -> None:
        await db_manager.set_setting(key, value)

    async def get_setting(self, key: str, default: Any = None) -> str | None:
        return await db_manager.get_setting(key, default=default)


def use_storage() -> Storage:
    """Return a Storage facade. Stateless — safe to call on every render."""
    return Storage()
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/app_next/test_use_storage.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check src/app_next/hooks/ tests/app_next/test_use_storage.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/app_next/hooks/ tests/app_next/test_use_storage.py
git commit -m "feat(app_next.hooks): use_storage async facade over db_manager

Thin dataclass wrapper exposing the subset of db_manager needed by
app_next components. M1 wires only set_setting/get_setting; further
methods added per milestone."
```

---

## Task 4: `use_focus_scope` — declarative `FocusScope` component replacing the counter hack

**Files:**
- Create: `src/app_next/hooks/use_focus_scope.py`
- Create: `tests/app_next/test_focus_scope.py`

**Why:** The legacy `core/focus_manager.py` keeps a module-level `_tab_index_counter` and a stateful `FocusManager(page)` object — global mutable state we don't want in the rewrite. Flet's `Control.focusable` + `Control.autofocus` (verified in `flet/controls/control.py`) cover spatial traversal. All we need is a `KeyboardListener` that fires `on_back` for Back/Escape. Verified APIs: `ft.KeyboardListener` constructor takes `on_key_event` + `content`; `KeyboardEvent` exposes `.key` as a string.

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_focus_scope.py`:

```python
"""Tests for the FocusScope component."""

from unittest import mock

import flet as ft
import pytest

from app_next.hooks.use_focus_scope import FocusScope


def test_focus_scope_assigns_autofocus_to_wrapped_container():
    """The root container autofocuses so the first focusable child wins."""
    scope = FocusScope(child=ft.Text("hi"))
    # FocusScope returns a KeyboardListener wrapping a Container with autofocus
    assert isinstance(scope, ft.KeyboardListener)
    inner = scope.content
    assert isinstance(inner, ft.Container)
    assert inner.autofocus is True


def test_focus_scope_passes_child_through():
    text = ft.Text("hi")
    scope = FocusScope(child=text)
    assert scope.content.content is text


@pytest.mark.parametrize("key", ["Back", "Escape", "BrowserBack", "Go Back"])
async def test_on_back_fires_for_back_keys(key):
    received = []
    fake_event = mock.Mock(spec=ft.KeyboardEvent)
    fake_event.key = key
    fake_event.ctrl = False
    fake_event.shift = False
    fake_event.alt = False
    fake_event.meta = False

    async def on_back(e):
        received.append(e)

    scope = FocusScope(child=ft.Text("x"), on_back=on_back)
    # Invoke the registered on_key_event the way Flet would.
    await scope.on_key_event(fake_event)
    assert received == [fake_event]


@pytest.mark.parametrize(
    "key", ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Tab"]
)
async def test_on_back_does_not_fire_for_navigation_keys(key):
    received = []
    fake_event = mock.Mock(spec=ft.KeyboardEvent)
    fake_event.key = key
    fake_event.ctrl = False
    fake_event.shift = False
    fake_event.alt = False
    fake_event.meta = False

    async def on_back(e):
        received.append(e)

    scope = FocusScope(child=ft.Text("x"), on_back=on_back)
    await scope.on_key_event(fake_event)
    assert received == []


async def test_on_back_optional_works_without_handler():
    """If on_back is None, back keys fall through silently (Flutter handles)."""
    fake_event = mock.Mock(spec=ft.KeyboardEvent)
    fake_event.key = "Back"
    fake_event.ctrl = False
    fake_event.shift = False
    fake_event.alt = False
    fake_event.meta = False
    scope = FocusScope(child=ft.Text("x"))  # no on_back
    await scope.on_key_event(fake_event)  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_focus_scope.py -v
```

Expected: `ModuleNotFoundError: No module named 'app_next.hooks.use_focus_scope'`.

- [ ] **Step 3: Implement FocusScope**

Create `src/app_next/hooks/use_focus_scope.py`:

```python
"""FocusScope — declarative back-key capture for TV-remote + desktop Esc.

Replaces the legacy `core/focus_manager.py` pattern (a module-level counter
+ stateful manager object). Spatial D-pad traversal is delegated entirely
to Flutter's DirectionalFocusTraversalPolicy: every interactive control
under the scope must declare `focusable=True`, and the relevant one
declares `autofocus=True`. The scope only catches Back/Escape so a parent
screen can pop the view stack or trigger app back.

Verified APIs (Flet 0.86.3 in .venv):
- `ft.KeyboardListener(content=..., on_key_event=...)` wraps any Control.
- `Control.autofocus: bool` (defaults False) — first True wins on mount.
- `ft.KeyboardEvent` exposes `.key: str` plus modifier flags.
"""

from collections.abc import Awaitable, Callable
from typing import Optional

import flet as ft
from flet.controls.control import Control

# Keys the Material platform emits for system Back. Verified against legacy
# `core/focus_manager.py` line 31 (same set kept for parity).
_BACK_KEYS = frozenset({"Back", "Escape", "BrowserBack", "Go Back"})


@ft.component
def FocusScope(
    child: Control,
    autofocus_root: bool = True,
    on_back: Optional[Callable[[ft.KeyboardEvent], Awaitable[None] | None]] = None,
) -> Control:
    """Wrap child in a KeyboardListener that fires `on_back` on Back/Escape.

    Args:
        child: the control tree to mount under the scope.
        autofocus_root: when True (default) the wrapping Container autofocuses
            on mount, causing Flutter to pass focus to the nearest focusable
            descendant. Set False when nesting multiple FocusScopes.
        on_back: optional async-or-sync callback receiving the KeyboardEvent.
            If omitted, Back/Escape just propagate (which on Flutter/Material
            translates to the system back action).
    """

    async def handle_key(e: ft.KeyboardEvent) -> None:
        if e.key in _BACK_KEYS and on_back is not None:
            result = on_back(e)
            if hasattr(result, "__await__"):
                await result

    return ft.KeyboardListener(
        on_key_event=handle_key,
        content=ft.Container(
            autofocus=autofocus_root,
            content=child,
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/app_next/test_focus_scope.py -v
```

Expected: all 17 parametrised cases + the autofocus tests pass.

If you see `TypeError` claiming `@ft.component` requires a function (not arbitrary callable) — re-check that the decorator is on a plain `def` (it is, above). If Flet complains that `handle_key` needs a particular signature, note that `_trigger_event` (verified in `base_control.py`) dispatches a 0- or 1-arg async handler — `handle_key(e)` is correct.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check src/app_next/hooks/use_focus_scope.py tests/app_next/test_focus_scope.py
```

Expected: clean. (If ruff flags `Optional` vs `X | None` inconsistency, use the modern form and drop the `typing` import — the codebase already uses `X | None` style in `main.py`; match it.)

- [ ] **Step 6: Commit**

```bash
git add src/app_next/hooks/use_focus_scope.py tests/app_next/test_focus_scope.py
git commit -m "feat(app_next.hooks): declarative FocusScope replacing global counter

Wraps a child in a KeyboardListener that fires on_back on Back/Escape.
Autofocus is set on the wrapping Container so Flutter's traversal policy
passes focus to the nearest focusable descendant on mount. Drops the
module-level counter hack — no global state, no per-page manager object."
```

---

## Task 5: `LoadingState` component

**Files:**
- Create: `src/app_next/components/__init__.py`
- Create: `src/app_next/components/loading_state.py`
- Create: `tests/app_next/test_loading_state.py`

**Why:** The onboarding offline retry button and later screens all need a centered "loading" placeholder. Single responsibility — a tiny component worth testing for shape (centered progress + label).

**Verified API:** `ft.ProgressRing()` and `ft.Container(alignment=ft.alignment.center)` are standard.

- [ ] **Step 1: Write the failing test**

Create `src/app_next/components/__init__.py`:

```python
```

Create `tests/app_next/test_loading_state.py`:

```python
"""Tests for LoadingState component."""

import flet as ft

from app_next.components.loading_state import LoadingState


def test_loading_state_is_a_container():
    """The component returns a Container with a ProgressRing and Text."""
    state = LoadingState(label="Working...")
    assert isinstance(state, ft.Container)
    # The container wraps a Column [ProgressRing, Text]
    inner = state.content
    assert isinstance(inner, ft.Column)
    types = [type(c) for c in inner.controls]
    assert ft.ProgressRing in types
    assert ft.Text in types


def test_loading_state_uses_label_text():
    state = LoadingState(label="Booting")
    inner = state.content
    texts = [c for c in inner.controls if isinstance(c, ft.Text)]
    assert texts and texts[0].value == "Booting"


def test_loading_state_defaults_label_when_none_given():
    state = LoadingState(label=None)
    inner = state.content
    texts = [c for c in inner.controls if isinstance(c, ft.Text)]
    # A default placeholder label is used when label is None.
    assert texts and texts[0].value
    assert texts[0].value != "Booting"


def test_loading_state_centered():
    state = LoadingState(label="x")
    assert state.alignment == ft.alignment.center
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_loading_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'app_next.components.loading_state'`.

- [ ] **Step 3: Implement LoadingState**

Create `src/app_next/components/loading_state.py`:

```python
"""LoadingState — a centered progress ring + label, for in-screen waits."""

import flet as ft
from flet.controls.control import Control

_DEFAULT_LABEL = "Loading..."


@ft.component
def LoadingState(label: str | None = None) -> Control:
    return ft.Container(
        alignment=ft.alignment.center,
        expand=True,
        content=ft.Column(
            controls=[
                ft.ProgressRing(),
                ft.Text(label or _DEFAULT_LABEL),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/app_next/test_loading_state.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check src/app_next/components/ tests/app_next/test_loading_state.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/app_next/components/ tests/app_next/test_loading_state.py
git commit -m "feat(app_next.components): LoadingState centered progress+label"
```

---

## Task 6: `OfflineFlow` component

**Files:**
- Create: `src/app_next/components/offline_flow.py`
- Create: `tests/app_next/test_offline_flow.py`

**Why:** Onboarding shows this when the channel fetch fails. Two buttons: Retry (re-runs the channel probe) and Skip to Offline (uses `"Other"` as country and proceeds). Buttons pass `on_retry` / `on_skip` callbacks up to the parent so the parent owns the async work and the loading state.

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_offline_flow.py`:

```python
"""Tests for OfflineFlow component."""

from unittest import mock

import flet as ft

from app_next.components.offline_flow import OfflineFlow


def test_offline_flow_renders_two_buttons():
    flow = OfflineFlow(on_retry=lambda e: None, on_skip=lambda e: None)
    assert isinstance(flow, ft.Container)
    buttons = list(_walk_buttons(flow))
    labels = " ".join(_button_label(b) for b in buttons)
    assert "Retry" in labels
    assert "Offline" in labels


def test_offline_flow_retry_button_wired_to_callback():
    fired = []
    flow = OfflineFlow(
        on_retry=lambda e: fired.append("retry"),
        on_skip=lambda e: None,
    )
    retry_btn = _find_button_by_label(flow, "Retry")
    assert retry_btn is not None
    assert retry_btn.on_click is not None
    # Simulate click
    retry_btn.on_click(mock.Mock())
    assert fired == ["retry"]


def test_offline_flow_skip_button_wired_to_callback():
    fired = []
    flow = OfflineFlow(
        on_retry=lambda e: None,
        on_skip=lambda e: fired.append("skip"),
    )
    skip_btn = _find_button_by_label(flow, "Offline")
    assert skip_btn is not None
    skip_btn.on_click(mock.Mock())
    assert fired == ["skip"]


# --- helpers ---


def _walk(control):
    """Yield all controls in the tree depth-first."""
    yield control
    children = getattr(control, "controls", None) or []
    if isinstance(children, list):
        for c in children:
            yield from _walk(c)
    content = getattr(control, "content", None)
    if content is not None:
        yield from _walk(content)


def _walk_buttons(root):
    for c in _walk(root):
        if isinstance(
            c, (ft.FilledButton, ft.OutlinedButton, ft.ElevatedButton, ft.TextButton)
        ):
            yield c


def _button_label(btn):
    content = btn.content
    if isinstance(content, ft.Text):
        return content.value or ""
    return getattr(btn, "text", "") or ""
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_offline_flow.py -v
```

Expected: `ModuleNotFoundError: No module named 'app_next.components.offline_flow'`.

- [ ] **Step 3: Implement OfflineFlow**

Create `src/app_next/components/offline_flow.py`:

```python
"""OfflineFlow — retry / skip-to-offline surface shown when channels won't load."""

import flet as ft
from flet.controls.control import Control


@ft.component
def OfflineFlow(on_retry, on_skip) -> Control:
    """Render a centered card with a Retry and a Skip-to-offline button.

    on_retry / on_skip are called with the click event. The parent component
    owns async behavior + loading state — OfflineFlow itself is stateless so
    it can be re-rendered by the parent without losing references to handlers.
    """
    from core.theme import AppColors  # local import keeps the component file thin

    return ft.Container(
        alignment=ft.alignment.center,
        expand=True,
        content=ft.Column(
            controls=[
                ft.Icon(ft.Icons.CLOUD_OFF, size=64, color=AppColors.GREY_DIM),
                ft.Text(
                    "Can't connect to the channel directory.",
                    text_align=ft.TextAlign.CENTER,
                    size=16,
                ),
                ft.Text(
                    "You can retry, or continue in offline mode with your local videos.",
                    text_align=ft.TextAlign.CENTER,
                    size=13,
                    color=AppColors.GREY_DIM,
                ),
                ft.FilledButton(
                    content=ft.Text("Retry Connection"),
                    icon=ft.Icons.REFRESH,
                    on_click=on_retry,
                ),
                ft.OutlinedButton(
                    content=ft.Text("Continue Offline"),
                    on_click=on_skip,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/app_next/test_offline_flow.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check src/app_next/components/offline_flow.py tests/app_next/test_offline_flow.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/app_next/components/offline_flow.py tests/app_next/test_offline_flow.py
git commit -m "feat(app_next.components): OfflineFlow retry/skip surface"
```

---

## Task 7: `OnboardingScreen` component (the big one)

**Files:**
- Create: `src/app_next/screens/__init__.py`
- Create: `src/app_next/screens/onboarding_screen.py`
- Create: `tests/app_next/test_onboarding_screen.py`

**Why:** Replaces `views/onboarding.py` (245 lines) + `views/onboarding_country.py` (49) + `views/onboarding_offline.py` (83) — 377 lines of legacy closure-and-ref-based rendering — with one `@ft.component` using `use_state` for selected country / terms / loading / offline-flag, `on_mounted` for the connectivity probe, `use_storage()` for persistence, and `OfflineFlow` / `LoadingState` for the degraded states. Submit calls `db_manager.set_setting("user_country", …)` and `set_setting("accepted_terms", "true")` — the SAME keys `AppController.init()` (lines 65–71) reads, so on next launch `state.has_accepted_terms` flips to True and `AppShell` (Task 9) routes straight to the dashboard.

**Verified APIs:**
- `ft.on_mounted(fn)` — runs once after mount; `fn` may be async (verified — `hooks/use_effect.py` accepts `Callable[[], Any | Awaitable[Any]]`).
- `ft.use_state(initial)` returns `(value, set)`. Setter is sync but renders only the calling component (verified scheduler queue).
- `ft.use_ref(initial)` for mutable values that persist across renders without triggering re-render.
- `ft.KeyboardListener(content=..., on_key_event=...)` for back-key capture — but we wrap the whole screen in `FocusScope(...)` (Task 4) in AppShell, so this screen does not directly use KeyboardListener.
- `ft.ListView(build_controls_on_demand=True)` — verified the kwarg exists and defaults True; passing it explicitly documents intent.
- Component accesses the page via `from flet.controls.context import context; context.page` (verified in `flet/components/component.py` line 17).

**Design choices reflected in the code below:**
- Online form has the same layout as the legacy view — logo, welcome, subtitle, country picker in a bordered container, terms checkbox, "Start Watching" filled button.
- Country picker uses a virtualized `ListView` of `ListTile`s with `key=ft.ValueKey(c["name"])` so selection scroll state is preserved across re-renders.
- The terms checkbox and country selection drive the **disabled** state of the submit button, removing the need for SnackBars before submission (better UX — the user gets immediate visual feedback rather than a modal toast). However, we still fall back to `page.show_dialog(SnackBar(...))` if `on_complete` raises (matches the migration pattern just committed).
- On offline: `OfflineFlow` handles Retry / Skip. Retry re-runs the probe; Skip calls `on_complete` after persisting a default `"Other"` country.

- [ ] **Step 1: Write the failing tests**

Create `src/app_next/screens/__init__.py`:

```python
```

Create `tests/app_next/test_onboarding_screen.py`:

```python
"""Tests for OnboardingScreen component logic.

We keep screen tests focused on the logic that's easy to verify off-screen:
the persistence side-effects of submit/skip, and the gating that decides
whether submit is enabled. Heavy rendering is exercised by integration
smoke tests (Task 10) which mount the component under a fake page.
"""

from unittest import mock

import pytest

from app_next.screens.onboarding_screen import (
    OnboardingScreen,
    _persist_terms_and_country,
    _persist_offline_defaults,
    can_submit,
)


@pytest.mark.parametrize(
    "country,terms,expected",
    [
        ("Nigeria", True, True),
        ("Nigeria", False, False),
        ("", True, False),
        ("", False, False),
    ],
)
def test_can_submit(country, terms, expected):
    assert can_submit(country, terms) is expected


async def test_persist_terms_and_country_writes_both_keys():
    storage = mock.AsyncMock()
    state = mock.Mock()
    await _persist_terms_and_country(storage=storage, state=state, country="Nigeria")
    storage.set_setting.assert_any_await("user_country", "Nigeria")
    storage.set_setting.assert_any_await("accepted_terms", "true")
    assert state.user_country == "Nigeria"
    assert state.has_accepted_terms is True
    assert state.is_first_launch is False


async def test_persist_offline_defaults_writes_other_country():
    storage = mock.AsyncMock()
    state = mock.Mock()
    await _persist_offline_defaults(storage=storage, state=state)
    storage.set_setting.assert_any_await("user_country", "Other")
    storage.set_setting.assert_any_await("accepted_terms", "true")
    assert state.user_country == "Other"
    assert state.has_accepted_terms is True
    assert state.is_first_launch is False


def test_onboarding_screen_is_component_callable():
    """The screen is a @ft.component — calling it builds a Component."""
    # The decorator turns it into a wrapper that needs an active renderer.
    # We assert the wrapper exists and is marked as a component.
    assert getattr(OnboardingScreen, "__is_component__", False) is True
    assert callable(OnboardingScreen)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_onboarding_screen.py -v
```

Expected: `ModuleNotFoundError: No module named 'app_next.screens.onboarding_screen'`.

- [ ] **Step 3: Implement OnboardingScreen**

Create `src/app_next/screens/onboarding_screen.py`:

```python
"""OnboardingScreen — first-launch country select + terms acceptance.

A @ft.component that owns four pieces of local state with use_state:
selected_country, terms_accepted, is_loading, is_offline.

Online flow:  Image + Welcome + Tagline + CountryPicker + Terms + Start.
Offline flow: OfflineFlow (retry re-runs probe, skip persists defaults).

Persistence calls write the SAME keys AppController.init() reads (see
src/main.py lines 65-71): `user_country` and `accepted_terms=true`. On
success we flip the observable `state.has_accepted_terms` so the parent
AppShell re-renders to the dashboard without page.update().

The actual connectivity probe (load_channels) is supplied by the caller
through the `prober` kwarg so this component is testable without a real
network.

OBSERVABLE SUBSCRIPTION NOTE: We access global state via
`ft.use_context(AppStateCtx)` rather than a plain `from ... import state`.
This matters because `use_context` automatically attaches an
ObservableSubscription to the component when the resolved value is an
Observable (verified in
.venv/lib/python3.13/site-packages/flet/components/hooks/use_context.py
lines 105-106). A plain import would NOT subscribe — so when
`state.channels` populates WHILE `_run_probe` is running, this component
would never re-render. Use `use_context` for any Component that needs to
react to global state changes.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import flet as ft
from flet.controls.control import Control

from app_next.components.loading_state import LoadingState
from app_next.components.offline_flow import OfflineFlow
from app_next.hooks.use_storage import Storage, use_storage
from app_next.state.app_state import AppStateCtx
from core.constants import (
    LBL_PLEASE_ACCEPT_TERMS,
    LBL_PLEASE_SELECT_COUNTRY,
    LBL_SELECT_COUNTRY,
    LBL_START_WATCHING,
    LBL_TV_NAV_HINT,
    LBL_USAGE_AGREEMENT,
    LBL_WELCOME,
    LBL_WELCOME_SUB,
    TERMS_TEXT,
)
from core.theme import AppColors


def can_submit(country: str, terms: bool) -> bool:
    """Submit is enabled only when a country is selected AND terms checked."""
    return bool(country) and bool(terms)


async def _persist_terms_and_country(
    storage: Storage, state: Any, country: str
) -> None:
    """Persist the user's country + terms acceptance and flip observable state.

    Writes `user_country=<name>` and `accepted_terms=true` — the SAME keys
    `AppController.init()` reads on next launch. Mutates the provided
    observable state so the parent AppShell re-renders automatically.
    """
    await storage.set_setting("user_country", country)
    await storage.set_setting("accepted_terms", "true")
    state.user_country = country
    state.has_accepted_terms = True
    state.is_first_launch = False


async def _persist_offline_defaults(storage: Storage, state: Any) -> None:
    """Skip-to-offline: default country to 'Other' and accept terms."""
    await storage.set_setting("user_country", "Other")
    await storage.set_setting("accepted_terms", "true")
    state.user_country = "Other"
    state.has_accepted_terms = True
    state.is_first_launch = False


@ft.component
def OnboardingScreen(
    countries: list[dict],
    on_complete: Callable[[], Awaitable[None] | None],
    prober: Callable[[], Awaitable[bool]] | None = None,
) -> Control:
    """Render the first-launch onboarding.

    Args:
        countries: list of {"name": "...", ...} dicts from ChannelProvider.
        on_complete: called (sync or async) after the user submits or skips.
        prober: optional async callable returning True when channels loaded
            successfully. Defaults to a probe that checks `state.channels`.
    """
    selected_country, set_selected_country = ft.use_state("")
    terms_accepted, set_terms_accepted = ft.use_state(False)
    is_loading, set_is_loading = ft.use_state(False)
    is_offline, set_is_offline = ft.use_state(False)
    storage = use_storage()
    # Subscribe to global observable state via context — see the OBSERVABLE
    # SUBSCRIPTION NOTE in this file's docstring. A plain `from ... import state`
    # would NOT subscribe. (Because AppState is @ft.observable, use_context
    # auto-attaches an ObservableSubscription; mutating state.channels or
    # state.has_accepted_terms elsewhere triggers re-render of THIS screen.)
    state = ft.use_context(AppStateCtx)

    async def _default_probe() -> bool:
        return bool(state.channels)

    probe = prober or _default_probe

    async def _run_probe():
        set_is_loading(True)
        try:
            ok = await probe()
            set_is_offline(not ok)
        finally:
            set_is_loading(False)

    ft.on_mounted(_run_probe)

    async def _on_retry(e):
        set_is_offline(False)
        await _run_probe()

    async def _on_skip(e):
        await _persist_offline_defaults(storage, state)
        await _maybe_invoke(on_complete)

    async def _on_submit(e):
        if not terms_accepted:
            _notify_warning(LBL_PLEASE_ACCEPT_TERMS)
            return
        if not selected_country:
            _notify_warning(LBL_PLEASE_SELECT_COUNTRY)
            return
        await _persist_terms_and_country(storage, state, selected_country)
        await _maybe_invoke(on_complete)

    if is_loading:
        return LoadingState(label="Connecting...")

    if is_offline:
        return OfflineFlow(on_retry=_on_retry, on_skip=_on_skip)

    return _build_online_form(
        countries=countries,
        selected_country=selected_country,
        on_select=set_selected_country,
        terms_accepted=terms_accepted,
        on_terms_toggle=set_terms_accepted,
        on_submit=_on_submit,
    )


# --- helpers (kept module-level so tests can import them without a renderer) ---


async def _maybe_invoke(fn: Callable[[], Awaitable[None] | None]) -> None:
    result = fn()
    if hasattr(result, "__await__"):
        await result


def _notify_warning(msg: str) -> None:
    """Show a SnackBar-as-dialog warning. Best-effort — swallow if no page."""
    from flet.controls.context import context

    try:
        page = context.page
        page.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=AppColors.WARNING))
    except Exception:
        pass


def _build_online_form(
    countries: list[dict],
    selected_country: str,
    on_select: Callable[[str], None],
    terms_accepted: bool,
    on_terms_toggle: Callable[[bool], None],
    on_submit: Callable[[Any], Awaitable[None]],
) -> Control:
    """Build the online country + terms form."""
    country_list = ft.ListView(
        controls=[_country_tile(c, selected_country, on_select) for c in countries],
        height=180,
        spacing=2,
        padding=5,
        build_controls_on_demand=True,
    )

    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        padding=ft.padding.symmetric(horizontal=40),
        content=ft.ListView(
            controls=[
                ft.Container(height=30),
                ft.Column(
                    controls=[
                        ft.Image(
                            src="/icon.png", width=90, height=90, border_radius=20
                        ),
                        ft.Text(
                            LBL_WELCOME,
                            size=34,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            LBL_WELCOME_SUB,
                            size=15,
                            text_align=ft.TextAlign.CENTER,
                            color=AppColors.GREY_DIM,
                            width=400,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
                ft.Divider(height=24, color=ft.Colors.TRANSPARENT),
                ft.Text(
                    LBL_SELECT_COUNTRY,
                    size=18,
                    weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    LBL_TV_NAV_HINT,
                    size=12,
                    color=AppColors.GREY_DIM,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Container(
                    content=country_list,
                    border=ft.Border.all(1.5, AppColors.PRIMARY),
                    border_radius=16,
                    padding=6,
                ),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.Container(
                    content=ft.Text(TERMS_TEXT, size=12, color=AppColors.GREY_DIM),
                    padding=16,
                    border_radius=14,
                    border=ft.Border.all(1, AppColors.GREY_DIM),
                ),
                ft.Row(
                    controls=[
                        ft.Checkbox(
                            value=terms_accepted,
                            on_change=lambda e: on_terms_toggle(e.control.value),
                        ),
                        ft.Text(
                            LBL_USAGE_AGREEMENT, size=14, weight=ft.FontWeight.W_500
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                    wrap=True,
                ),
                ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
                ft.FilledButton(
                    content=ft.Text(
                        LBL_START_WATCHING, size=16, weight=ft.FontWeight.W_600
                    ),
                    on_click=on_submit,
                    disabled=not can_submit(selected_country, terms_accepted),
                    width=float("inf"),
                ),
                ft.Container(height=30),
            ],
            expand=True,
            spacing=10,
        ),
    )


def _country_tile(
    country: dict,
    selected_country: str,
    on_select: Callable[[str], None],
) -> ft.ListTile:
    name = country.get("name", "")
    is_selected = name == selected_country
    return ft.ListTile(
        key=ft.ValueKey(name),
        title=ft.Text(
            name,
            color=ft.Colors.WHITE if is_selected else None,
            weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL,
        ),
        leading=ft.Icon(
            ft.Icons.CHECK_CIRCLE if is_selected else ft.Icons.RADIO_BUTTON_UNCHECKED,
            color=ft.Colors.WHITE if is_selected else AppColors.GREY_DIM,
        ),
        on_click=lambda e, n=name: on_select(n),
        dense=True,
        shape=ft.RoundedRectangleBorder(radius=8),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run pytest tests/app_next/test_onboarding_screen.py -v
```

Expected: 6 passed (4 parametrised `can_submit` + 2 persistence + 1 callable check).

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check src/app_next/screens/ tests/app_next/test_onboarding_screen.py
```

Expected: clean. If ruff complains about the `Any` import being unused, drop it; if it complains `Callable` should be `collections.abc.Callable`, adjust — both styles are present elsewhere in the codebase; pick `collections.abc` since the file already imports it.

- [ ] **Step 6: Commit**

```bash
git add src/app_next/screens/__init__.py src/app_next/screens/onboarding_screen.py tests/app_next/test_onboarding_screen.py
git commit -m "feat(app_next.screens): OnboardingScreen component with hooks

Replaces views/onboarding.py + onboarding_country.py + onboarding_offline.py
(~377 lines) with a single @ft.component using use_state for selected
country/terms/loading/offline and on_mounted for the connectivity probe.
Persists the SAME keys AppController.init() reads (user_country,
accepted_terms=true) and flips observable state so AppShell re-renders."
```

---

## Task 8: `PlaceholderScreen` component (M1 stand-in for Home/Search/Local/Settings)

**Files:**
- Create: `src/app_next/screens/placeholder_screen.py`
- Create: `tests/app_next/test_placeholder_screen.py`

**Why:** The new shell wires all 4 NavigationBar destinations in M1, but only Onboarding and the placeholder need to exist before M2 ships them properly. The placeholder is also useful as a smoke render target for AppShell tests (Task 9). Full Home/Search/Local/Settings implementations ship in M2–M4.

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_placeholder_screen.py`:

```python
"""Tests for the M1 placeholder screen."""

import flet as ft

from app_next.screens.placeholder_screen import PlaceholderScreen


def test_placeholder_is_container_with_named_text():
    p = PlaceholderScreen(name="Home")
    assert isinstance(p, ft.Container)
    inner = p.content
    assert isinstance(inner, ft.Column)
    texts = [c for c in inner.controls if isinstance(c, ft.Text)]
    assert any("Home" in (t.value or "") for t in texts)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_placeholder_screen.py -v
```

Expected: `ModuleNotFoundError: No module named 'app_next.screens.placeholder_screen'`.

- [ ] **Step 3: Implement PlaceholderScreen**

Create `src/app_next/screens/placeholder_screen.py`:

```python
"""M1 placeholder for the four dashboard screens.

Real implementations: Home (M2), Search (M3), Local (M3),
Settings (M4). The placeholder exists so AppShell's NavigationBar can
route to all four destinations during M1 without crashing. Each tab shows
the destination name plus the milestone it lands in, so dev/test runs
make the in-progress status obvious.
"""

import flet as ft
from flet.controls.control import Control

_MILESTONE_BY_NAME = {
    "Home": "M2",
    "Search": "M3",
    "Local": "M3",
    "Settings": "M4",
}


@ft.component
def PlaceholderScreen(name: str = "Unknown") -> Control:
    milestone = _MILESTONE_BY_NAME.get(name, "?")
    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        content=ft.Column(
            controls=[
                ft.Icon(ft.Icons.CONSTRUCTION, size=64),
                ft.Text(
                    f"{name} screen",
                    size=24,
                    weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    f"Lands in milestone {milestone}.",
                    color=ft.Colors.ON_SURFACE_VARIANT,
                    size=13,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/app_next/test_placeholder_screen.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Lint**

Run:

```bash
uv run ruff check src/app_next/screens/placeholder_screen.py tests/app_next/test_placeholder_screen.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add src/app_next/screens/placeholder_screen.py tests/app_next/test_placeholder_screen.py
git commit -m "feat(app_next.screens): M1 PlaceholderScreen for nav destinations"
```

---

## Task 9: `AppShell` — top-level component, NavigationBar, branch to Onboarding vs scaffold

**Files:**
- Create: `src/app_next/app_shell.py`
- Modify: `src/app_next/__init__.py` (export `AppShell`)
- Create: `tests/app_next/test_app_shell.py`
- Modify: `tests/app_next/test_env_toggle.py` — remove the `xfail` marker from `test_init_renders_shell_when_env_next`

**Why:** `AppShell` is the component `page.render(AppShell)` calls (Task 1's branch). It subscribes to `AppStateCtx`, decides between Onboarding (when `is_first_launch or not has_accepted_terms`) and the dashboard scaffold, and renders a NavigationBar with 4 destinations switching local state. It wires `FocusScope` around the whole tree so the system Back key on TV remotes pops the view stack. After this task the next-branch test added in Task 1 finally goes green and we un-xfail it.

**Verified API fact recap:**
- `ft.on_mounted(fn)` — runs once after the shell mounts; we use it to restore the channel list (`AppController.load_channels`) via a context-provided callback from the controller, so the shell doesn't import the controller.

  …but `AppController.load_channels` is bound to the controller instance. We don't pass `controller` to `AppShell` directly because `page.render(AppShell)` (Task 1) calls it with no args. We need a second channel to inject the controller's methods into the tree. **Solution: `ControllerMethodsCtx`** — a context whose default value is a `ControllerMethods` dataclass of no-op callbacks; `AppController.init` (in the next-branch path) mounts a `ContextProvider(ControlerMethodsCtx, value=ControllerMethods(refresh_channels=controller.load_channels, play_stream=controller.play_stream, pop_views=self._handle_back, ...))` just before calling `page.render(AppShell)`.

  This adds a small complication. To keep M1 minimal, we ship `ControllerMethodsCtx` with **no-op defaults** and wire only `refresh_channels` from `AppController`. The other callbacks get wired when their owning screens (M2–M4) are built — using a no-op default now means the shell renders without crashing even if a screen misbehaves.

- `ft.use_state(0)` for selected tab index.
- `ft.use_view_path()` returns the current route, useful for deep-link `/play?url=…` detection — but we verified that `AppController.route_change` already intercepts deep links **before** shell mounts (it's called in `main()` and pushes a View directly). So the shell only sees `/dashboard`, `/search`, `/local`, `/settings`. For the offline fragments `/play?url=…` we trust the controller to handle.

- [ ] **Step 1: Add `ControllerMethodsCtx`**

Create `src/app_next/state/controller_ctx.py`:

```python
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
    return None


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
```

**Note on the type-mismatch pitfall:** the default callables must match the field signatures *exactly*. Earlier drafts used sync `_noop_async` returning `None` for an `Awaitable[None]` field — that would have been a `TypeError` at the point an `await controller.refresh_channels()` call happened (awaiting a `None`). The above version uses real `async def` no-ops for both awaits — keep it that way if you extend the dataclass in later milestones.

- [ ] **Step 2: Write the failing test for AppShell**

Create `tests/app_next/test_app_shell.py`:

```python
"""Tests for AppShell top-level component.

We exercise the observable-driven branch: AppShell renders OnboardingScreen
when the user hasn't accepted terms, and the dashboard scaffold (Column +
NavigationBar + PlaceholderScreen) when terms are accepted. Because
@ft.component rendering requires an active renderer/page session, we run
the shell through `Renderer().render(...)` directly and inspect the
returned control tree.
"""

import flet as ft

from app_next.app_shell import AppShell, _should_show_onboarding, _dashboard_scaffold
from app_next.state.app_state import state as app_state
from core.state import state as core_singleton


def test_should_show_onboarding_when_first_launch():
    """Helper mirrors the branch in AppShell."""
    app_state.reset()
    app_state.is_first_launch = True
    app_state.has_accepted_terms = False
    assert _should_show_onboarding(app_state) is True


def test_should_show_onboarding_when_terms_not_accepted():
    app_state.reset()
    app_state.is_first_launch = False
    app_state.has_accepted_terms = False
    assert _should_show_onboarding(app_state) is True


def test_should_not_show_onboarding_when_terms_accepted():
    app_state.reset()
    app_state.is_first_launch = False
    app_state.has_accepted_terms = True
    assert _should_show_onboarding(app_state) is False


def test_dashboard_scaffold_has_4_destinations_and_keyed_body():
    """The dashboard builder returns a Column with a NavigationBar of 4
    destinations and a body keyed by the active tab."""
    body = _dashboard_scaffold(selected_tab=1, on_change=lambda i: None)
    assert isinstance(body, ft.Column)
    nav = next((c for c in body.controls if isinstance(c, ft.NavigationBar)), None)
    assert nav is not None
    assert len(nav.destinations) == 4
    assert nav.selected_index == 1


def test_dashboard_scaffold_destinations_have_expected_labels():
    body = _dashboard_scaffold(selected_tab=0, on_change=lambda i: None)
    nav = next((c for c in body.controls if isinstance(c, ft.NavigationBar)), None)
    labels = [d.label for d in nav.destinations]
    assert labels == ["Home", "Search", "Local", "Settings"]


def test_app_state_singleton_alias_works():
    """Sanity: the state exported from app_next IS the legacy singleton."""
    assert app_state is core_singleton


def test_app_shell_is_marked_as_component():
    assert getattr(AppShell, "__is_component__", False) is True


def test_app_shell_source_uses_use_context_for_state(capsys):
    """Regression guard: AppShell MUST use ft.use_context(AppStateCtx), NOT a
    plain `from app_next.state.app_state import state`. The auto-subscription
    that use_context attaches is what makes Onboarding → dashboard
    transition fire when state.has_accepted_terms flips. If a future edit
    replaces use_context with a plain import, this test catches it.

    We assert by inspecting the source file directly — this is the only
    practical way without an active component renderer. (Renderer-level
    assertion lives in test_integration_smoke.py's manual smoke step.)
    """
    import inspect
    from app_next import app_shell

    source = inspect.getsource(app_shell)
    assert "use_context(AppStateCtx)" in source, (
        "AppShell must access state via use_context(AppStateCtx) — see the "
        "OBSERVABLE SUBSCRIPTION RULE in src/app_next/state/app_state.py."
    )
    # Also assert the plain-import form is NOT present (sans the docstring).
    code_lines = [
        line
        for line in source.splitlines()
        if not line.strip().startswith(("#", '"""', "'''"))
    ]
    code = "\n".join(code_lines)
    assert "from app_next.state.app_state import state" not in code
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_app_shell.py -v
```

Expected: `ModuleNotFoundError: No module named 'app_next.app_shell'`.

- [ ] **Step 4: Implement AppShell**

Create `src/app_next/app_shell.py`:

```python
"""AppShell — top-level @ft.component rendered via page.render(AppShell).

Branches between OnboardingScreen and the dashboard scaffold based on the
observable AppState. Owns NavigationBar selected-index as use_state. Wraps
the whole tree in FocusScope so the Android TV / Fire Stick Back key pops
the view stack via ControllerMethodsCtx.pop_views.

Routing note: deep-link routes (`ktv://play?url=…`) are intercepted by
AppController.route_change BEFORE AppShell mounts, so the shell only ever
sees /dashboard, /search, /local, /settings. We trust the controller to
push /play Views above the shell.
"""

import flet as ft
from flet.controls.control import Control

from app_next.hooks.use_focus_scope import FocusScope
from app_next.screens.onboarding_screen import OnboardingScreen
from app_next.screens.placeholder_screen import PlaceholderScreen
from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from channels.provider import channel_provider

_TAB_NAMES = ("Home", "Search", "Local", "Settings")
_TAB_ICONS = (
    ft.Icons.HOME,
    ft.Icons.SEARCH,
    ft.Icons.FOLDER,
    ft.Icons.SETTINGS,
)


def _should_show_onboarding(s) -> bool:
    """Mirror of the branch in AppShell — exported for tests."""
    return s.is_first_launch or not s.has_accepted_terms


def _dashboard_scaffold(
    selected_tab: int,
    on_change: "callable[[int], None]",
) -> ft.Column:
    """Build the dashboard body: a 4-destination NavigationBar keyed body.

    Exported separately so tests can assert the NavigationBar shape without
    needing an active renderer.
    """
    destinations = [
        ft.NavigationBarDestination(icon=icon, label=label)
        for icon, label in zip(_TAB_ICONS, _TAB_NAMES, strict=True)
    ]
    body = PlaceholderScreen(
        key=ft.ValueKey(_TAB_NAMES[selected_tab]), name=_TAB_NAMES[selected_tab]
    )
    return ft.Column(
        controls=[
            ft.Container(content=body, expand=True),
            ft.NavigationBar(
                destinations=destinations,
                selected_index=selected_tab,
                on_change=lambda e: on_change(e.control.selected_index),
            ),
        ],
        expand=True,
        spacing=0,
    )


async def _onboarding_complete() -> None:
    """No-op default — the real completion handler lives on AppController.

    Onboarding writes `accepted_terms=true` to DB + flips observable state;
    once `state.has_accepted_terms` becomes True the shell re-renders to the
    dashboard on its own (no explicit navigation). Nothing to do here.
    """


@ft.component
def AppShell() -> Control:
    """Top-level shell. Reads observable state; renders Onboarding or dashboard."""
    selected_tab, set_selected_tab = ft.use_state(0)
    controller = ft.use_context(ControllerMethodsCtx)

    # CRITICAL: app state is accessed via use_context, NOT a plain import.
    # use_context auto-attaches an ObservableSubscription when the resolved
    # value is an Observable (verified in
    # .venv/lib/python3.13/site-packages/flet/components/hooks/use_context.py
    # lines 105-106). Without this, flipping state.has_accepted_terms inside
    # OnboardingScreen's submit handler would NOT cause AppShell to re-render
    # from the Onboarding branch to the dashboard branch — the user would be
    # stuck on Onboarding after pressing "Start Watching".
    state = ft.use_context(AppStateCtx)

    if _should_show_onboarding(state):
        countries = channel_provider.get_countries()
        screen = OnboardingScreen(
            countries=countries,
            on_complete=_onboarding_complete,
        )
    else:
        screen = _dashboard_scaffold(
            selected_tab=selected_tab,
            on_change=set_selected_tab,
        )

    async def _on_back(e):
        controller.pop_views()

    return FocusScope(child=screen, on_back=_on_back)
```

- [ ] **Step 5: Export AppShell from the package**

Update `src/app_next/__init__.py`:

```python
"""New Flet-component-based frontend for KTV Player.

Gated behind KTV_FRONTEND=next until cutover. See
docs/superpowers/specs/2026-07-28-frontend-rewrite-design.md.
"""

from app_next.app_shell import AppShell

__all__ = ["AppShell"]
```

- [ ] **Step 6: Wire `AppController` to mount the controller context provider in next mode**

Update the env-flag branch in `AppController.init` (the block we added in Task 1):

```python
        # Frontend mount point. When KTV_FRONTEND=next, hand the page over to
        # the new component tree; AppShell owns routing, theme syncing, and
        # the NavigationBar. The legacy code path below is untouched.
        if _frontend_is_next():
            from app_next import AppShell
            from app_next.state.controller_ctx import (
                ControllerMethods,
                ControllerMethodsCtx,
            )

            methods = ControllerMethods(
                refresh_channels=self.load_channels,
                play_stream=self.play_stream,
                pop_views=self._handle_back,
            )
            self.page.render(
                lambda _self=methods: ft.ContextProvider(
                    ControllerMethodsCtx, value=_self, child=AppShell()
                )
            )
            return
```

But `page.render(component_fn, *args)` calls `Renderer().render(component_fn, *args)`, which itself calls `component_fn(...)`. So passing a `lambda` that returns a `ContextProvider(child=AppShell())` works directly — the ContextProvider becomes the root control, AppShell is its child, and `use_context(ControllerMethodsCtx)` inside AppShell resolves to `methods`.

**Why the `_self=methods` default-arg trick on the lambda:** Flet's `Renderer` calls the supplied callable with no positional arguments. If you close over `methods` directly (without the default-arg binding), Python would also close over later mutations — but here `methods` is built once and never reassigned, so a plain closure works too. The default-arg form is defensive against future refactors that might rebind `methods`. You may simplify to `lambda: ft.ContextProvider(...)` if you prefer.

Note: `page.render(...)` puts Flet in components mode, in which the renderer expects to call the supplied callable once to produce a root control. Our lambda fits that contract.

- [ ] **Step 7: Un-xfail the next-branch test**

Edit `tests/app_next/test_env_toggle.py`:

Replace the top of the file's failing marker:

```python
import os
from unittest import mock

import flet as ft

import pytest

from src.main import AppController


def _make_controller(fake_page):
    """Build an AppController without calling init()."""
    return AppController(fake_page)


async def test_init_renders_shell_when_env_next(fake_page, monkeypatch):
    """When KTV_FRONTEND=next, init() ends with page.render(AppShell)."""
    monkeypatch.setenv("KTV_FRONTEND", "next")
    controller = _make_controller(fake_page)
```

I.e., delete the `@pytest.mark.xfail(reason="AppShell lands in Task 9")` line. Also update the assertion: the rendered component is now a lambda, NOT `AppShell` directly — so the test should assert that `page.render` was called exactly once (and optionally that calling the lambda with a ContextProvider returns a control containing AppShell):

```python
# init() should have called page.render exactly once.
assert len(fake_page.render_calls) == 1
render_callable = fake_page.render_calls[0][0]

# The render callable should return something that has AppShell as a
# descendant. Easiest: call it once and unwrap.
from app_next import AppShell

root = render_callable()
# ContextProvider wraps a Control whose identity we assert.
assert root is not None
# The child of the ContextProvider is AppShell (as a Component).
# We don't deeply inspect the rendered tree here; asserting render was
# called and root is truthy is enough for M1. (Component identity match
# is exercised in tests/app_next/test_app_shell.py.)
```

Leave the legacy test (`test_init_does_not_render_shell_when_env_legacy`) untouched.

- [ ] **Step 8: Run all M1 tests + legacy suite**

Run:

```bash
uv run pytest -q
uv run ruff check src/ tests/
```

Expected: full suite green (legacy tests + all `tests/app_next/*`). No new ruff warnings.

If `test_init_renders_shell_when_env_next` is still failing, the most common cause is that `page.render` is recorded with the lambda AND the ContextProvider constructor needs a different signature in this Flet patch. Check the source:

```bash
grep -n "class ContextProvider\|def ContextProvider\|ContextProvider(" \
  .venv/lib/python3.13/site-packages/flet/components/hooks/use_context.py
```

`ContextProvider(context_provider, value, child)` — confirmed signature. If the kwarg names differ (e.g. `default`), adjust.

- [ ] **Step 9: Commit**

```bash
git add src/app_next/ src/main.py tests/app_next/test_app_shell.py tests/app_next/test_env_toggle.py
git commit -m "feat(app_next): AppShell top-level component + NavigationBar scaffold

AppShell renders OnboardingScreen when first-launch/unaccepted terms,
else a 4-destination NavigationBar + keyed PlaceholderScreen body.
Wraps the tree in FocusScope so the TV remote Back key pops views via
ControllerMethodsCtx.pop_views. AppController mounts a ContextProvider
holding ControllerMethods (refresh_channels/play_stream/pop_views) before
page.render(AppShell) so components get controller callbacks by context.

Un-xfails the Task 1 next-branch test now that AppShell exists."
```

---

## Task 10: Integration smoke render + plan close-out

**Files:**
- Create: `tests/app_next/test_integration_smoke.py`
- Modify: `docs/superpowers/plans/2026-07-28-milestone1-frontend-scaffold.md` (this file) — append a "Done" summary section at the very bottom after exec.

**Why:** All previous tasks prove individual pieces work. This task mounts `AppShell` for real — through `ft.Page.render`-equivalent wiring, on both branches (first-launch and returning user) — and asserts no exception is raised and the resulting control tree contains an OnboardingScreen or a NavigationBar as appropriate. The whole point is to catch renderer-level mismatches (e.g. `ContextProvider` signature drift between this plan and the installed Flet) before declaring M1 done.

**Verified API:** `Renderer().render(component_fn)` (from `flet/components/component.py`) is what `page.render(component_fn)` calls internally — same effect, no Page object needed for a render smoke test in 0.86.3.

- [ ] **Step 1: Write the integration smoke test (helper-level)**

`Renderer` from `flet.components.component` is an internal class (not in the
public `ft.*` namespace — verified by grepping `flet/__init__.py`). Calling
it from tests would couple us to internals and break across patch versions.
We therefore keep this test at the **helper layer** (the exact module-level
functions AppShell delegates to) and rely on Task 10 Step 5's manual smoke
for true renderer-level validation. This is more robust than reaching into
Flet internals.

Create `tests/app_next/test_integration_smoke.py`:

```python
"""Integration smoke test (helper-layer) for AppShell.

Renderer-level / page.render smoke is done manually in
docs/superpowers/plans/2026-07-28-milestone1-frontend-scaffold.md Step 5.
Here we exercise the module-level helpers AppShell delegates to, end-to-end,
covering both branches and the controller-context wiring.
"""

import flet as ft

from app_next.app_shell import (
    AppShell,
    _dashboard_scaffold,
    _should_show_onboarding,
)
from app_next.state.app_state import state
from app_next.state.controller_ctx import (
    ControllerMethods,
    ControllerMethodsCtx,
)
from core.state import state as core_singleton


def test_should_show_onboarding_false_when_returning_user():
    state.reset()
    state.is_first_launch = False
    state.has_accepted_terms = True
    assert _should_show_onboarding(state) is False


def test_dashboard_scaffold_has_4_destinations():
    body = _dashboard_scaffold(selected_tab=2, on_change=lambda i: None)
    assert isinstance(body, ft.Column)
    nav = next(c for c in body.controls if isinstance(c, ft.NavigationBar))
    assert nav.selected_index == 2
    assert [d.label for d in nav.destinations] == [
        "Home",
        "Search",
        "Local",
        "Settings",
    ]


def test_dashboard_scaffold_body_uses_named_placeholder():
    body = _dashboard_scaffold(selected_tab=3, on_change=lambda i: None)
    # The first control is a Container wrapping the PlaceholderScreen.
    nav_target = body.controls[0]
    assert isinstance(nav_target, ft.Container)


def test_controller_methods_defaults_are_awaitable_no_ops():
    """Awaiting the default callbacks must not raise (no TypeError on awaiting None)."""
    import asyncio

    methods = ControllerMethods()
    asyncio.run(methods.refresh_channels())
    asyncio.run(methods.play_stream("http://x", None))
    methods.pop_views()


def test_controller_methods_ctx_default_is_a_controller_methods_instance():
    """Reading the context without a provider returns a usable ControllerMethods."""
    # create_context stores the default on the returned ContextProvider.
    default = ControllerMethodsCtx.default_value
    assert isinstance(default, ControllerMethods)


def test_onboarding_screen_source_uses_use_context_for_state():
    """Regression guard: OnboardingScreen must access state via use_context,
    NOT via a plain `from app_next.state.app_state import state as app_state`.
    Matches the same rule AppShell follows (see test_app_shell.py).
    """
    import inspect
    from app_next.screens import onboarding_screen

    source = inspect.getsource(onboarding_screen)
    assert "use_context(AppStateCtx)" in source
    # The plain-import antipattern must NOT appear in the rendered body.
    code_lines = [
        line
        for line in source.splitlines()
        if not line.strip().startswith(("#", '"""', "'''"))
    ]
    code = "\n".join(code_lines)
    assert "from app_next.state.app_state import state" not in code


def test_state_app_state_alias_is_core_singleton():
    assert state is core_singleton


def test_app_shell_is_marked_as_component():
    assert getattr(AppShell, "__is_component__", False) is True
```

- [ ] **Step 2: Run test to verify it passes**

Run:

```bash
uv run pytest tests/app_next/test_integration_smoke.py -v
```

Expected: 7 passed. (If `ControllerMethodsCtx.default_value` is not the right attribute to inspect — verify in `.venv/lib/python3.13/site-packages/flet/components/hooks/use_context.py` — that test should be adjusted to whatever the context's public getter is named. The intent is to assert the default object is a `ControllerMethods` instance so the screen falls through safely with no provider mounted. If the attribute is private, drop the test rather than reach into internals.)

- [ ] **Step 3: Lint**

Run:

```bash
uv run ruff check tests/app_next/test_integration_smoke.py
```

Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add tests/app_next/test_integration_smoke.py docs/superpowers/plans/2026-07-28-milestone1-frontend-scaffold.md
git commit -m "test(app_next): integration smoke render of AppShell + M1 closeout notes"
```

- [ ] **Step 5: Manual smoke (REQUIRED before declaring M1 done)**

In a terminal (with GUI):

```bash
KTV_FRONTEND=next uv run flet run src/main.py
```

Verify by eye:
1. Onboarding screen renders: logo, "Welcome", subtitle, country picker box with at least Nigeria in the list, terms checkbox, "Start Watching" button (disabled until you pick a country AND check the box).
2. Pick a country. Check the box. Button becomes enabled. Click it.
3. Dashboard scaffold renders: 4 destinations at the bottom (Home/Search/Local/Settings), "Home screen — Lands in milestone M2" placeholder in the middle.
4. Tap each of the four nav destinations — placeholder text changes accordingly; selection highlights the destination.
5. Close the app, run again WITHOUT `KTV_FRONTEND=next` (or with `KTV_FRONTEND=legacy`) — the legacy dashboard renders as before. This proves the env toggle doesn't affect the default path.

- [ ] **Step 6: Final regression sweep**

Run:

```bash
uv run pytest -q
uv run ruff check src/ tests/
```

Expected: full suite green, ruff clean.

- [ ] **Step 7: Open a draft PR against `main` titled "M1: Frontend scaffold + AppShell + Onboarding (env toggle)"

The PR body should summarize:
- Add `src/app_next/` parallel tree.
- `KTV_FRONTEND=next` env flag in `AppController.init` mounts `AppShell`.
- Onboarding + NavigationBar scaffold with placeholders.
- Focused regression: full pytest suite + ruff clean.
- Manual smoke on `KTV_FRONTEND=next flet run` performed.
- Legacy frontend untouched; deletion scheduled for M6.

---

## Done checklist (executor fills this in at the bottom when M1 ships)

- [ ] All 10 tasks committed
- [ ] `uv run pytest -q` green
- [ ] `uv run ruff check src/ tests/` clean
- [ ] Manual smoke on `KTV_FRONTEND=next flet run src/main.py` performed and the 5 onboarding → dashboard transitions verified
- [ ] Legacy frontend (default) still runs as before (no env var set)
- [ ] Draft PR opened against `main` with the M1 body above
- [ ] Self-review notes (below) addressed

## Self-review notes (filled at end of execution)

- Any deviation from this plan: record here, with reason.
- Anything discovered about Flet 0.86.3 that the plan got wrong: record here (e.g. exact `ContextProvider` signature).
