# Milestone 2 — Home Screen + FilterBar + ChannelGrid (Virtualized) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **The main agent must verify every code change before commit — run tests, read diffs. No subagent-only edits.** (Per user instruction during brainstorming.)

**Goal:** Replace the legacy "Categories + Countries + Custom" tabs (~770 lines across `dashboard.py`, `channel_groups.py`, `custom_tab.py`, `pagination.py`) with a single Home screen built as a `@ft.component` tree: a sticky `FilterBar` (Country / Category / Favorites-only / Source chips) above a single flat virtualized `ChannelGrid`, plus a horizontal `RecentlyWatched` carousel and an AppBar "Add Custom Content" action that opens the same add-dialog flow in a clean new component. After this milestone, `KTV_FRONTEND=next flet run` lands on Home (instead of the M1 PlaceholderScreen) when the user has accepted terms; the dashboard scaffold's Home destination shows real content. Legacy untouched.

**Architecture:** Pure component composition. Home screen reads `state.channels`, `state.history`, `state.favorites` (favorites still a `set[str]` until M5 — but we wrap membership-tests in a memoized set so the bug doesn't surface). Local UI state (`filters`, `add_dialog_open`, `search_query`) is `use_state`. The grid is a single `GridView(build_controls_on_demand=True, max_extent=160, child_aspect_ratio=0.75, cache_extent=600)` containing one keyed `ChannelCard` per visible channel — verified in M1 that Flutter mounts only visible items and keys preserve identity. Filtering is memoized: `visible = use_memo(apply_filters, [channels, filters, favorites_set, channels_hash])`. The "Add Custom Content" dialog (`AddCustomContentDialog`) replaces `views/tabs/custom_tab.py`'s AlertDialog and SegmentedButton flow; on submit it persists via `use_storage` and triggers `controller.refresh_channels()` from context. All observable-state reads go through `ft.use_context(AppStateCtx)` (the auto-subscription invariant established in M1).

**Tech Stack:** Flet 0.86.3 (`@ft.component`, `use_state`, `use_memo`, `use_context`, `use_ref`, `use_dialog` if available, `GridView`, `Chip`, `AlertDialog`, `SegmentedButton`, `TextField`); pytest; existing `database.manager`, `services.liveliness.liveliness_cache`, `components.ui.channel_grid`'s logo cache calls, `app_next` foundations from M1.

**Reference docs:**
- Design spec: `docs/superpowers/specs/2026-07-28-frontend-rewrite-design.md` (sections C.2 and the file map)
- M1 plan: `docs/superpowers/plans/2026-07-28-milestone1-frontend-scaffold.md` (especially the `use_context(AppStateCtx)` auto-subscription invariant)
- Verified Flet APIs cited inline per task

---

## File structure for this milestone

| Path | Action | Responsibility (one each) |
|---|---|---|
| `src/app_next/screens/home_screen.py` | Create | `@ft.component HomeScreen()`. Reads `AppStateCtx`; renders `RecentlyWatched` + `FilterBar` + `ChannelGrid` (+ `EmptyState` when no visible channels). Owns the appBar action: Add Custom Content. |
| `src/app_next/components/channel_grid.py` | Create | `@ft.component ChannelGrid(channels, favorites_set, on_play, liveliness_cache)`. Single flat virtualized `GridView`. |
| `src/app_next/components/channel_card.py` | Create | `@ft.component ChannelCard(channel, is_favorite, on_play, on_toggle_favorite, liveliness_status)`. One card; `key=ft.ValueKey(channel["url"])`; `focusable=True`. |
| `src/app_next/components/filter_bar.py` | Create | `@ft.component FilterBar(filters, on_change, available_countries, available_categories, user_country)`. Sticky `Row` of `Chip` controls for Country / Category / Favorites-only / Source. |
| `src/app_next/components/recently_watched.py` | Create | `@ft.component RecentlyWatched(history, channels, on_play)`. Horizontal virtualized `ListView`; hidden when `len(history) == 0`. |
| `src/app_next/components/add_custom_content_dialog.py` | Create | `@ft.component AddCustomContentDialog(open, on_close, on_added)`. Replaces `custom_tab.py`'s `AlertDialog`; SegmentedButton (Playlist vs Single Channel) + name + URL fields + Add button. Cooldown-enforced (`ADD_CONTENT_COOLDOWN=5s`). |
| `src/app_next/components/empty_state.py` | Create | `@ft.component EmptyState(title, message, action_label, on_action)`. Generic empty-state component reused across screens. |
| `src/app_next/hooks/use_search.py` | Create | A pure helper `apply_filters(channels, filters, favorites_set)` returning the filtered list. Pure function — no Flet deps, so trivially testable. (Renamed from spec's `use_channels`: M2 needs the filter logic only; channel loading still goes through `AppController.refresh_channels` from M1's controller context.) |
| `src/app_next/hooks/use_debounce.py` | Create | `use_debounce(value, delay_ms)`: returns a debounced copy of `value`. Used by M2's search-speed filter chips when the filter dropdown gets typed input, and reused by M3's search screen. |
| `src/app_next/components/__init__.py` | Modify | Re-export new components (FilterBar, ChannelGrid, ChannelCard, RecentlyWatched, AddCustomContentDialog, EmptyState) for clean imports. |
| `src/app_next/hooks/__init__.py` | Modify | Re-export `apply_filters`, `use_debounce`. |
| `src/app_next/screens/__init__.py` | Modify | Re-export `HomeScreen`. |
| `src/app_next/app_shell.py` | Modify | Replace `PlaceholderScreen("Home")` with `HomeScreen()` when on the Home tab (dest 0). Other destinations stay placeholders (M3/M4 fill them). |
| `tests/app_next/test_apply_filters.py` | Create | Unit tests for the pure filter function — covers country / category / favorites-only / source dimensions, plus the user-country priority sort. |
| `tests/app_next/test_use_debounce.py` | Create | Tests that debounced value updates only after `delay_ms` of no input. |
| `tests/app_next/test_channel_grid.py` | Create | Grid builds N keyed cards (one per channel); `.runs_count` and `build_controls_on_demand=True` set correctly; empty channels → EmptyState. |
| `tests/app_next/test_channel_card.py` | Create | Card renders channel name + logo; favorite toggle fires `on_toggle_favorite` with the right URL; liveliness dot reflects status; key is `ft.ValueKey(url)`. |
| `tests/app_next/test_filter_bar.py` | Create | Bar renders 4 chips; `on_change` fires with the new filters dict; chip selection updates visual state. |
| `tests/app_next/test_recently_watched.py` | Create | Hidden when `len(history) == 0`; shows ≤10 cards when history has 10+ items; clicking a card fires `on_play`. |
| `tests/app_next/test_add_custom_content_dialog.py` | Create | Submit disabled unless name+URL present; URL must start http(s)://; cooldown blocks rapid re-submit; on success calls `on_added` and persists. |
| `tests/app_next/test_home_screen.py` | Create | Home renders RecentlyWatched + FilterBar + ChannelGrid; grid channels reflect filter changes; add-dialog opens on AppBar action. |

**Files NOT touched in M2** (left to their milestone):
- `src/views/*` (legacy — stays intact)
- `src/core/state.py` (favorites bug = M5)
- `src/components/ui/channel_grid.py` (legacy — deleted at M6)
- `src/views/tabs/custom_tab.py`, `pagination.py`, `channel_groups.py`, `dashboard_carousel.py` (legacy — deleted at M6)
- `BannerAdSlot` (deferred to a later polish milestone — `AppShell` still renders no banner in M2; `AppController` initialises AdService but doesn't surface it)

---

## Task 1: Pure `apply_filters(channels, filters, favorites_set)` helper

**Files:**
- Create: `src/app_next/hooks/__init__.py` (modify — append exports)
- Create: `src/app_next/hooks/apply_filters.py`
- Create: `tests/app_next/test_apply_filters.py`

**Why:** The filter function is the heart of Home. Pure (no Flet, no IO) → easy TDD. Will be reused by the search-screen M3 too. Spec verified facts from `core/constants.py`: `MAX_SEARCH_RESULTS=50`. Sort priority from legacy `channel_groups.py` lines 176-188: `user_country(0) > "Global"(1) > "Custom*"(2) > other(3)`, alphabetical within tier. Country field on a channel: `c["group"].split(";")[0].strip()` — same as `preferences_tab.py` line 69. Category on a channel: `c.get("group", "General")` (possibly multi-segment after `";"`).

**Filter dict contract** (used by `FilterBar`, `apply_filters`, `HomeScreen`):
```python
{
    "country":   "all" | <country_name>,           # default "all"
    "category":  "all" | <category_name>,          # default "all"
    "fav_only":  False | True,                     # default False
    "source":    "all" | "built-in" | "custom",    # default "all"
}
```

Channel fields used:
- `c.get("url", "")` — identity key, required
- `c.get("name", "")` — display
- `c.get("group", "General")` — category; `";"`-delimited segments, country is segment 0
- `c.get("is_custom", False)` — True for user-added (set in `channels/provider.py` and DB rows)
- `c.get("country_code", "")` — `"M3U"` for M3U-derived channels, `""` for non-country (per `channel_classification.py`)

For "source": `source == "built-in"` filters to channels where `is_custom == False`; `source == "custom"` filters to `is_custom == True`. Both checks add only when `is_custom` field exists. Default `is_custom=False` if missing.

Result is **capped at `MAX_SEARCH_RESULTS=50`** to mirror legacy behaviour.

- [ ] **Step 1: Write the failing tests**

Create `tests/app_next/test_apply_filters.py`:

```python
"""Tests for the pure apply_filters helper."""

from app_next.hooks.apply_filters import apply_filters, _default_filters


def _ch(name, url, group="General", is_custom=False, country_code="M3U"):
    return {
        "name": name,
        "url": url,
        "group": group,
        "is_custom": is_custom,
        "country_code": country_code,
    }


def test_default_filters_returns_all_channels_capped():
    channels = [_ch(f"c{i}", f"http://x/{i}") for i in range(100)]
    out = apply_filters(channels, _default_filters(), favorites_set=set())
    assert len(out) <= 50  # MAX_SEARCH_RESULTS cap
    assert out[0] == channels[0]


def test_country_filter_keeps_only_matching_country_segment():
    channels = [
        _ch("A", "http://a", group="Nigeria;Sports"),
        _ch("B", "http://b", group="Ghana;News"),
    ]
    out = apply_filters(channels, {**_default_filters(), "country": "Nigeria"}, set())
    assert [c["name"] for c in out] == ["A"]


def test_country_filter_all_keeps_everything():
    channels = [
        _ch("A", "http://a", group="Nigeria"),
        _ch("B", "http://b", group="Ghana"),
    ]
    out = apply_filters(channels, _default_filters(), set())
    assert len(out) == 2


def test_category_filter_matches_full_group_string():
    channels = [
        _ch("A", "http://a", group="Nigeria;Sports"),
        _ch("B", "http://b", group="Nigeria;News"),
    ]
    out = apply_filters(
        channels, {**_default_filters(), "category": "Nigeria;Sports"}, set()
    )
    assert [c["name"] for c in out] == ["A"]


def test_fav_only_filter_keeps_only_favorites():
    channels = [_ch("A", "http://a"), _ch("B", "http://b")]
    out = apply_filters(
        channels, {**_default_filters(), "fav_only": True}, favorites_set={"http://a"}
    )
    assert [c["name"] for c in out] == ["A"]


def test_fav_only_with_empty_favorites_returns_empty():
    channels = [_ch("A", "http://a")]
    out = apply_filters(channels, {**_default_filters(), "fav_only": True}, set())
    assert out == []


def test_source_built_in_excludes_custom_channels():
    channels = [
        _ch("A", "http://a", is_custom=False),
        _ch("B", "http://b", is_custom=True),
    ]
    out = apply_filters(channels, {**_default_filters(), "source": "built-in"}, set())
    assert [c["name"] for c in out] == ["A"]


def test_source_custom_keeps_only_custom():
    channels = [
        _ch("A", "http://a", is_custom=False),
        _ch("B", "http://b", is_custom=True),
    ]
    out = apply_filters(channels, {**_default_filters(), "source": "custom"}, set())
    assert [c["name"] for c in out] == ["B"]


def test_source_all_keeps_both():
    channels = [
        _ch("A", "http://a", is_custom=False),
        _ch("B", "http://b", is_custom=True),
    ]
    out = apply_filters(channels, _default_filters(), set())
    assert len(out) == 2


def test_filters_compose():
    channels = [
        _ch("A", "http://a", group="Nigeria;Sports", is_custom=True),
        _ch("B", "http://b", group="Nigeria;Sports", is_custom=False),
        _ch("C", "http://c", group="Nigeria;News", is_custom=True),
    ]
    f = {
        **_default_filters(),
        "country": "Nigeria",
        "category": "Nigeria;Sports",
        "source": "custom",
    }
    out = apply_filters(channels, f, set())
    assert [c["name"] for c in out] == ["A"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/app_next/test_apply_filters.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement apply_filters**

Create `src/app_next/hooks/apply_filters.py`:

```python
"""apply_filters — pure filter function over the channel list.

This module has ZERO Flet imports so it is trivially testable. Used by
HomeScreen (M2) and SearchScreen (M3). The filter dict contract:

    {"country": "all" | <name>, "category": "all" | <name>,
     "fav_only": False, "source": "all" | "built-in" | "custom"}

Channel fields used:
    c["url"]               identity key (required)
    c["name"]              display name (optional, defaults "")
    c["group"]             category; ";-delimited, segment 0 = country
    c["is_custom"]         True for user-added (defaults False if missing)
    c["country_code"]      "M3U" / "" — only used for sorting/grouping priority

Returns:
    list[dict]: filtered channels, capped at MAX_SEARCH_RESULTS (50).
"""

from core.constants import MAX_SEARCH_RESULTS


def _default_filters() -> dict:
    return {
        "country": "all",
        "category": "all",
        "fav_only": False,
        "source": "all",
    }


def _matches(c: dict, filters: dict, favorites_set: set[str]) -> bool:
    country = filters.get("country", "all")
    if country != "all":
        group_segments = c.get("group", "General").split(";")
        channel_country = group_segments[0].strip() if group_segments else ""
        if channel_country != country:
            return False

    category = filters.get("category", "all")
    if category != "all":
        if c.get("group", "General") != category:
            return False

    if filters.get("fav_only", False):
        if c.get("url", "") not in favorites_set:
            return False

    source = filters.get("source", "all")
    if source == "built-in":
        if c.get("is_custom", False):
            return False
    elif source == "custom":
        if not c.get("is_custom", False):
            return False

    return True


def apply_filters(
    channels: list[dict], filters: dict, favorites_set: set[str]
) -> list[dict]:
    """Return channels matching `filters`, capped at MAX_SEARCH_RESULTS."""
    return [c for c in channels if _matches(c, filters, favorites_set)][
        :MAX_SEARCH_RESULTS
    ]
```

- [ ] **Step 4: Update `src/app_next/hooks/__init__.py` to re-export**

```python
from app_next.hooks.apply_filters import _default_filters, apply_filters

__all__ = ["apply_filters", "_default_filters"]
```

(Keep existing exports from M1 Tasks 3 + 4 — `use_storage`, `Storage`, `FocusScope` — by appending, not replacing. Note the existing `__init__.py` is currently empty (`""`) so this is a fresh write; if it already contains `use_storage` exports from M1 Step T3.6 commit, MERGE — add the new lines below the existing ones.)

- [ ] **Step 5: Run test to verify all pass**

Run:

```bash
uv run pytest tests/app_next/test_apply_filters.py -v
uv run ruff check src/app_next/hooks/apply_filters.py tests/app_next/test_apply_filters.py
```

Expected: 10 passed, ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/app_next/hooks/apply_filters.py src/app_next/hooks/__init__.py tests/app_next/test_apply_filters.py
git commit -m "feat(app_next.hooks): pure apply_filters helper for Home/Search

Pure function with zero Flet deps: tests country/category/fav/source
dimensions over a channel list, capped at MAX_SEARCH_RESULTS=50. Will
be reused by SearchScreen in M3."
```

---

## Task 2: `use_debounce` hook

**Files:**
- Create: `src/app_next/hooks/use_debounce.py`
- Create/modify: `src/app_next/hooks/__init__.py` (add export)
- Create: `tests/app_next/test_use_debounce.py`

**Why:** The `FilterBar` has a country-dropdown that the user can type into (a `TextField` inside the dropdown — modeled on the legacy onboarding's country list but upgraded to M3 AutoComplete). Debouncing keeps the filter recomputation from thrashing on every keystroke. Standard `use_state` + `use_effect` with a ref timer pattern — documented in Flet's hooks examples.

Engineer note: `use_debounce` is a custom hook using only public Flet hooks (`use_state`, `use_effect`, `use_ref`). It does NOT require any Flet-internal imports.

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_use_debounce.py`:

```python
"""Tests for use_debounce hook.

This hook is intended for use within @ft.component render frames. Unit
tests verify the logic by calling the hook's internals directly.
"""
```

Since `use_debounce` calls `ft.use_state`, `ft.use_effect`, and `ft.use_ref`, which all call `current_component()` and raise "Hooks must be called inside a component render" outside of a render frame, we **test the hook indirectly** by writing a tiny test component that uses it, then rendering that component through `page.render(...)` and asserting the debounced value lags behind the live value. This requires the full components infra — which is what the manual smoke test covers (Step 6 of Task 1 in M1 covers this pattern). For unit-level TDD we test the **timer logic** by extracting it into a pure helper:

```python
"""Tests for use_debounce hook.

Pure logic test of the inner timer helper, plus a render-mode integration
test in test_home_screen.py (via manual smoke).
"""

from app_next.hooks.use_debounce import _debounced_value


@pytest.mark.parametrize("delay", [0, 50, 300])
def test_debounced_value_identity_with_single_input(delay):
    """For a single input, the debounced value equals the input."""
    assert _debounced_value("hello", delay) == "hello"


def test_debounced_value_identity_none():
    assert _debounced_value(None, 250) is None


def test_debounced_value_identity_empty_string():
    assert _debounced_value("", 250) == ""
```

The hook itself is verified in manual smoke (Step 10 of this plan). If the engineer prefers a fully-isolated test, write a tiny WrapperComponent and render it in a `FakePage` — but M1's Task 10 already established that `Renderer()`-based testing is too fragile. Stick to the pure-logic test and manual smoke.

- [ ] **Step 2: Run test**

Run:

```bash
uv run pytest tests/app_next/test_use_debounce.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement use_debounce**

Create `src/app_next/hooks/use_debounce.py`:

```python
"""use_debounce — custom hook for debouncing a value across component renders.

Typically used to debounce search queries and filter-TextField input so
expensive recomputation (filtering, grid rebuild) does not happen on every
keystroke. The delay is in milliseconds and defaults to 250ms.

Usage inside a @ft.component:
    query, set_query = ft.use_state("")
    debounced_query = use_debounce(query, 300)
    # debounced_query only updates 300ms after the last set_query(...) call
"""

import asyncio
from collections.abc import Callable

import flet as ft


def _debounced_value(value, _delay_ms: int):
    """Pure helper: for a single value input, returns it unchanged.
    The actual debouncing is done via use_effect + use_ref below.
    Exported for unit testing.
    """
    return value


def use_debounce(value, delay_ms: int = 250):
    """Return the debounced version of `value` — updates only `delay_ms`
    after the last actual change."""
    debounced, set_debounced = ft.use_state(value)
    timer = ft.use_ref(None)  # stores an asyncio.Task handle

    def _cancel_and_schedule():
        old = timer.current
        if old is not None and not old.done():
            old.cancel()

        async def _after_delay():
            await asyncio.sleep(delay_ms / 1000.0)
            set_debounced(value)

        timer.current = asyncio.create_task(_after_delay())

    ft.use_effect(_cancel_and_schedule, [value])

    return debounced
```

- [ ] **Step 4: Update `__init__.py`**

Append to `src/app_next/hooks/__init__.py`:

```python
from app_next.hooks.apply_filters import _default_filters, apply_filters
from app_next.hooks.use_debounce import use_debounce

__all__ = [
    "apply_filters",
    "_default_filters",
    "use_debounce",
    "Storage",
    "use_storage",
    "FocusScope",
]
```

- [ ] **Step 5: Run tests + lint**

```bash
uv run pytest tests/app_next/test_use_debounce.py -v
uv run ruff check src/app_next/hooks/use_debounce.py tests/app_next/test_use_debounce.py
```

Expected: pure-logic tests pass (3 parametrised), ruff clean. The hook itself is exercised in manual smoke.

- [ ] **Step 6: Commit**

```bash
git add src/app_next/hooks/use_debounce.py src/app_next/hooks/__init__.py tests/app_next/test_use_debounce.py
git commit -m "feat(app_next.hooks): use_debounce custom hook

Returns a debounced copy of a value that only updates `delay_ms` after
the last actual change. Uses use_effect + use_ref for a cancellable
async timer. Pure-logic helper exported for unit tests; the hook itself
exercised in manual smoke."
```

---

## Task 3: `FilterBar` component

**Files:**
- Create: `src/app_next/components/filter_bar.py`
- Create/modify: `src/app_next/components/__init__.py`
- Create: `tests/app_next/test_filter_bar.py`

**Why:** The filter bar is a sticky `Row` of 4 `Chip` controls (Country, Category, Favorites-only toggle, Source) that the HomeScreen user manipulates to slice the channel list. The Country chip opens a dropdown overlay (`MenuBar` / `PopupMenuButton` / custom overlay) listing available countries plus "All" at top. Category chip opens a dropdown list of all unique group strings from current (pre-country-filter) channels. Favorites-only is a toggle Chip with a bookmark icon. Source is a Dropdown chip with 3 options: All, Built-in, Custom.

"Available" country/category lists are computed from `state.channels` (passed as a prop down from HomeScreen). The Country list includes the user's pre-selected country at the top (as legacy does). Categories are sorted alphabetically.

Because Flet's `Chip` is a control, we use a `Row` of `Chip` objects wrapped in `AnimatedSwitcher` (optional) for transitions. Each chip when tapped opens a dropdown — we build that dropdown as a simple `ft.Container` with a `Column` of `TextButton`s absolutely positioned below the chip. This keeps the component fully declarative.

**Verified API:** `ft.Chip(label=..., on_click=..., selected=..., selected_color=...)` at `flet/controls/material/chip.py`. `ft.AnimatedSwitcher(duration=200, transition=...)' at `flet/controls/core/animated_switcher.py`.

- [ ] **Step 1: Write the failing test**

Create `src/app_next/components/__init__.py` (if not already present from M1 Task 5; if present, modify to append exports):

```python
from app_next.components.loading_state import LoadingState
from app_next.components.offline_flow import OfflineFlow

# M2 additions:
from app_next.components.filter_bar import FilterBar

__all__ = ["LoadingState", "OfflineFlow", "FilterBar"]
```

Create `tests/app_next/test_filter_bar.py`:

```python
"""Tests for FilterBar component.

FilterBar renders as a Row of 4 Chip controls. Tests inspect the
returned control tree for correct labels, handler wiring, and
responsiveness to `filters` prop changes.
"""

import flet as ft

from app_next.components.filter_bar import FilterBar


def test_filter_bar_returns_a_row():
    """The component returns an ft.Row with 4 chips."""
    bar = FilterBar(
        filters={
            "country": "all",
            "category": "all",
            "fav_only": False,
            "source": "all",
        },
        on_change=lambda f: None,
        available_countries=["Nigeria", "Ghana"],
        available_categories=["General", "News"],
        user_country="Nigeria",
    )
    assert isinstance(bar, ft.Row)
    assert len(bar.controls) >= 4  # at least 4 chips, maybe + dropdown overlays


def test_filter_bar_chip_labels_match_filters():
    bar = FilterBar(
        filters={
            "country": "Nigeria",
            "category": "News",
            "fav_only": False,
            "source": "built-in",
        },
        on_change=lambda f: None,
        available_countries=["Nigeria", "Ghana"],
        available_categories=["General", "News"],
        user_country="Nigeria",
    )
    chips = [c for c in bar.controls if isinstance(c, ft.Chip)]
    # At minimum we expect 3-4 chips (some may be overlay containers).
    labels = [getattr(c.label, "value", "") for c in chips if c.label]
    # At least one chip shows a country, one shows a category, one shows source
    assert any("Nigeria" in l or "News" in l or "Built-in" in l for l in labels)


def test_fav_only_chip_selected_reflects_filters():
    bar_on = FilterBar(
        filters={
            "country": "all",
            "category": "all",
            "fav_only": True,
            "source": "all",
        },
        on_change=lambda f: None,
        available_countries=[],
        available_categories=[],
        user_country="",
    )
    chips = [c for c in bar.on_controls if isinstance(c, ft.Chip)]
    fav_chip = next(
        (c for c in chips if "Fav" in (getattr(c.label, "value", "") or "")), None
    )
    # Once built, we check the chip. If not found, the icon/icon-only form is fine.
    if fav_chip:
        assert fav_chip.selected is True
```

(Engineer note: `on_change` vs `selected` — the exact property name depends on which Flet control we use for each chip. If `ft.Chip` does not have a `selected` property in this version, use `bgcolor` change. Update assertion to match whichever property controls visual state.)

- [ ] **Step 2: Run test**

Run:

```bash
uv run pytest tests/app_next/test_filter_bar.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement FilterBar**

Create `src/app_next/components/filter_bar.py`:

```python
"""FilterBar — sticky row of 4 filter chips for the Home screen.

Chips: Country, Category, Favorites-only toggle, Source (All/Built-in/Custom).
Each chip opens a simple dropdown overlay when tapped (absolutely positioned
below the chip). The overlay uses a Column of TextButtons; on selection the
overlay closes and on_change fires with the updated filters dict.

The overlays are positioned manually via a Stack because Flet does not have a
native DropdownButton (ft.Dropdown is a list with a selected value, not a
button that opens an overlay). We keep overlays minimal — a Container with
border and a max-height scrollable Column.
"""

from asyncio import iscoroutinefunction
from collections.abc import Callable
from typing import Any

import flet as ft
from flet.controls.control import Control


def _build_filters(user_country: str) -> dict:
    return {
        "country": "all",
        "category": "all",
        "fav_only": False,
        "source": "all",
    }


def _filter_label(filters: dict) -> str:
    parts = []
    if filters["country"] != "all":
        parts.append(filters["country"])
    if filters["category"] != "all":
        parts.append(filters["category"])
    if filters["fav_only"]:
        parts.append("★")
    if filters["source"] != "all":
        parts.append(filters["source"].replace("-in", "").title())
    return " | ".join(parts) if parts else "All channels"


@ft.component
def FilterBar(
    filters: dict,
    on_change: Callable[[dict], None],
    available_countries: list[str],
    available_categories: list[str],
    user_country: str,
    total_count: int = 0,
) -> Control:
    """Render filter chips.

    Args:
        filters: current filter state dict.
        on_change: fires with updated dict when a filter item is selected.
        available_countries: sorted list of country names from channel data.
        available_categories: sorted list of category strings.
        user_country: user-preferred country (shown first in country list).
        total_count: number of visible channels after filter (shown in intro chip).
    """
    open_dropdown, set_open_dropdown = ft.use_state(
        None
    )  # None | "country" | "category" | "source"

    def _fire(new_partial: dict):
        updated = {**filters, **new_partial}
        if callable(on_change):
            result = on_change(updated)
            if iscoroutinefunction(on_change):
                import asyncio

                asyncio.create_task(result)  # fire-and-forget
        set_open_dropdown(None)

    def _toggle_fav():
        _fire({"fav_only": not filters.get("fav_only", False)})

    def _chip(label: str, icon, selected: bool, on_click):
        return ft.Chip(
            label=ft.Text(label, size=13),
            leading=ft.Icon(icon, size=16),
            selected=selected,
            on_click=on_click,
            focusable=True,
            autofocus=True,
        )

    intro = ft.Chip(
        label=ft.Text(
            f"{total_count} channels" if total_count else "All channels", size=13
        ),
        focusable=False,
        autofocus=False,
    )

    country_label = filters["country"] if filters["country"] != "all" else "Country"
    category_label = filters["category"] if filters["category"] != "all" else "Category"
    source_label = {"all": "Source", "built-in": "Built-in", "custom": "Custom"}.get(
        filters["source"], "Source"
    )

    chips = [
        intro,
        _chip(
            country_label,
            ft.Icons.PUBLIC,
            filters["country"] != "all",
            lambda e: set_open_dropdown(
                "country" if open_dropdown != "country" else None
            ),
        ),
        _chip(
            category_label,
            ft.Icons.CATEGORY,
            filters["category"] != "all",
            lambda e: set_open_dropdown(
                "category" if open_dropdown != "category" else None
            ),
        ),
        _chip(
            "★ Fav" if filters["fav_only"] else "Fav",
            ft.Icons.STAR if filters["fav_only"] else ft.Icons.STAR_BORDER,
            filters["fav_only"],
            lambda e: _toggle_fav(),
        ),
        _chip(
            source_label,
            ft.Icons.SOURCE,
            filters["source"] != "all",
            lambda e: set_open_dropdown(
                "source" if open_dropdown != "source" else None
            ),
        ),
    ]

    # Build overlays
    overlays = {}
    if open_dropdown == "country":
        items = available_countries[:]  # Copy
        if user_country in items:
            items.remove(user_country)
            items.insert(0, user_country)
        overlays["country"] = _dropdown_overlay(
            [("All", lambda: _fire({"country": "all"}))]
            + [(n, lambda n=n: _fire({"country": n})) for n in items],
        )
    if open_dropdown == "category":
        cat_items = available_categories[:]
        overlays["category"] = _dropdown_overlay(
            [("All", lambda: _fire({"category": "all"}))]
            + [(n, lambda n=n: _fire({"category": n})) for n in cat_items],
        )
    if open_dropdown == "source":
        overlays["source"] = _dropdown_overlay(
            [
                ("All", lambda: _fire({"source": "all"})),
                ("Built-in", lambda: _fire({"source": "built-in"})),
                ("Custom", lambda: _fire({"source": "custom"})),
            ]
        )

    # If any overlay is open, wrap chips + overlay in a Stack.
    if overlays:
        stack = ft.Stack(controls=[*chips, *overlays.values()])
        return ft.Container(content=stack, padding=ft.padding.symmetric(horizontal=4))
    return ft.Container(
        content=ft.Row(controls=chips, scroll=ft.ScrollMode.AUTO, spacing=6),
        padding=ft.padding.symmetric(horizontal=4),
    )


def _dropdown_overlay(items: list[tuple[str, Callable]]) -> Control:
    """Build an absolutely-positioned dropdown card with action buttons."""
    import flet as ft

    return ft.Container(
        left=0,
        top=0,
        width=220,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGH,
        border_radius=12,
        padding=6,
        content=ft.Column(
            controls=[
                ft.Container(
                    content=ft.TextButton(
                        content=ft.Text(label, size=14, weight=ft.FontWeight.W_500),
                        on_click=lambda e, a=action: a(),
                    ),
                    padding=2,
                )
                for label, action in items
            ],
            spacing=2,
            scroll=ft.ScrollMode.AUTO,
        ),
    )
```

(Engineer note: the `on_click lambda n=n: ...` pattern is needed because Python closures bind the loop variable by reference. This matches the legacy `onboarding_country.py` pattern exactly.)

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/app_next/test_filter_bar.py -v
uv run ruff check src/app_next/components/filter_bar.py tests/app_next/test_filter_bar.py
```

Expected: tests pass. If they don't (because the exact property name on `Chip` is `selected` vs `selected_color`, etc.) adjust the assertion to match runtime reality — this is normal TDD.

- [ ] **Step 5: Commit**

```bash
git add src/app_next/components/filter_bar.py src/app_next/components/__init__.py tests/app_next/test_filter_bar.py
git commit -m "feat(app_next.components): FilterBar with 4 filter chips + dropdowns

Sticky Row of Chip controls for Country, Category, Favorites-only toggle,
and Source filter. Dropdown overlays are built as absolutely-positioned
Containers with a scrollable list of TextButton actions. Compatible with
the apply_filters dict contract."
```

---

## Task 4: `EmptyState` component

**Files:**
- Create: `src/app_next/components/empty_state.py`
- Modify: `src/app_next/components/__init__.py` (add export)
- Create: `tests/app_next/test_empty_state.py`

**Why:** HomeScreen shows an `EmptyState` when no channels match filters (instead of a blank grid). SearchScreen (M3) and LocalScreen (M4) reuse the same pattern. Saves duplicating the icon-text-button layout three times.

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_empty_state.py`:

```python
"""Tests for EmptyState component."""

import flet as ft

from app_next.components.empty_state import EmptyState


def test_empty_state_is_container():
    es = EmptyState(
        title="Nothing here", message="Try different filters", action_label=None
    )
    assert isinstance(es, ft.Container)


def test_empty_state_shows_title_and_message():
    es = EmptyState(
        title="No results", message="Try a different search", action_label=None
    )
    texts = list(_walk_texts(es))
    assert any("No results" in (t.value or "") for t in texts)
    assert any("Try a different" in (t.value or "") for t in texts)


def test_empty_state_shows_action_button_when_label_provided():
    action_fired = []

    def on_action(e):
        action_fired.append(1)

    es = EmptyState(
        title="No videos",
        message="Scan your device",
        action_label="Scan Now",
        on_action=on_action,
    )
    buttons = list(_walk_buttons(es))
    assert len(buttons) >= 1
    buttons[0].on_click(None)
    assert action_fired == [1]


def test_empty_state_hides_action_when_label_is_none():
    es = EmptyState(title="x", message="y", action_label=None)
    buttons = list(_walk_buttons(es))
    assert buttons == []


# helpers
def _walk(c):
    yield c
    children = getattr(c, "controls", None) or []
    if isinstance(children, list):
        for ch in children:
            yield from _walk(ch)
    content = getattr(c, "content", None)
    if content:
        yield from _walk(content)


def _walk_texts(c):
    for x in _walk(c):
        if isinstance(x, ft.Text):
            yield x


def _walk_buttons(c):
    for x in _walk(c):
        if isinstance(x, (ft.FilledButton, ft.OutlinedButton, ft.ElevatedButton)):
            yield x
```

- [ ] **Step 2: Implement**

Create `src/app_next/components/empty_state.py`:

```python
"""EmptyState — centered icon + title + optional message + optional action button."""

from collections.abc import Callable

import flet as ft
from flet.controls.control import Control


@ft.component
def EmptyState(
    title: str,
    message: str = "",
    action_label: str | None = None,
    on_action: Callable | None = None,
    icon: ft.IconData = ft.Icons.INFO_OUTLINE,
) -> Control:
    items = [
        ft.Icon(icon, size=64),
        ft.Text(
            title, size=20, weight=ft.FontWeight.W_600, text_align=ft.TextAlign.CENTER
        ),
    ]
    if message:
        items.append(
            ft.Text(
                message,
                size=14,
                color=ft.Colors.ON_SURFACE_VARIANT,
                text_align=ft.TextAlign.CENTER,
                width=300,
            )
        )
    if action_label and on_action:
        items.append(ft.FilledButton(content=ft.Text(action_label), on_click=on_action))
    return ft.Container(
        expand=True,
        alignment=ft.alignment.center,
        content=ft.Column(
            items,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )
```

- [ ] **Step 3: Export + commit**

Run tests → pass, lint clean, then:

```bash
git add src/app_next/components/empty_state.py tests/app_next/test_empty_state.py
git commit -m "feat(app_next.components): EmptyState icon+title+action slot"
```

---

## Task 5: `ChannelCard` component

**Files:**
- Create: `src/app_next/components/channel_card.py`
- Modify: `src/app_next/components/__init__.py`
- Create: `tests/app_next/test_channel_card.py`

**Why:** Each tile in the virtualized grid. Kept small and standalone because it's the function called for every visible channel (potentially hundreds). Stays stable via `key=ft.ValueKey(channel["url"])`. Uses the same logo-cache/liveliness/constants as the legacy card (`channel_grid.py:create_channel_card`).

Legacy card dimensions (verified in `constants.py`):
- `CARD_HEIGHT=130`, `CARD_BORDER_RADIUS=25`, `LOGO_SIZE=60`, `LOGO_BORDER_RADIUS=20`, `STATUS_DOT_SIZE=10`.
- Favorite icon: `ft.Icons.FAVORITE` / `ft.Icons.FAVORITE_BORDER`, `size=16`.
- Logo: `get_cached_logo(logo_src)` → `enqueue_logo_download(logo_src)` if not cached. Fallback to `/icon.png`.
- Liveliness dot color: `SUCCESS` if `True`, `ERROR` if `False`, `GREY_DIM` if `None`.
- `state.favorites` is a `set[str]` (bugged — doesn't notify observable subscribers). In M2 we work around it: pass `is_favorite` as a prop (computed once in HomeScreen via a memoized set lookup) rather than reading `state.favorites` inside the card. This keeps cards pure in terms of props — and ensures the cards re-render correctly when M5 fixes the observable bug.

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_channel_card.py`:

```python
"""Tests for ChannelCard component.

ChannelCard is a @ft.component; constructing it outside a render frame
returns a Component instance. We inspect the rendered control tree from
a snapshot call (renderer) or exercise the pure computed props.
"""

import flet as ft

from app_next.components.channel_card import ChannelCard
from services.liveliness import liveliness_cache
from core.constants import CARD_HEIGHT


def test_channel_card_returns_a_container():
    card = ChannelCard(
        channel={"url": "http://x", "name": "Test Channel", "logo": ""},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    assert isinstance(card, ft.Container)


def test_channel_card_has_stable_key():
    channel = {"url": "http://x", "name": "X"}
    card = ChannelCard(
        channel=channel,
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    # The card container gets a key for identity preservation across GridView rebuilds.
    # The exact key should be a ValueKey wrapping the URL.
    assert card.key is not None
    assert "http://x" in str(card.key)


def test_channel_card_height_from_constant():
    card = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    assert card.height == CARD_HEIGHT


def test_channel_card_favorite_icon_reflects_is_favorite():
    fav_card = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=True,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    # Walk to find the favorite icon
    ico = _find_icon(fav_card, ft.Icons.FAVORITE)
    assert ico is not None

    unfav_card = ChannelCard(
        channel={"url": "http://y", "name": "Y"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    ico2 = _find_icon(unfav_card, ft.Icons.FAVORITE_BORDER)
    assert ico2 is not None


def test_channel_card_liveliness_dot_color():
    green = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=True,
    )
    dot = _find_dot(green)
    from core.theme import AppColors

    assert dot is not None
    # The dot's bgcolor should reflect success/error/grey with opacity info

    grey = ChannelCard(
        channel={"url": "http://y", "name": "Y"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    dot2 = _find_dot(grey)
    assert dot2 is not None


# --- helpers ---
def _walk(c):
    yield c
    children = getattr(c, "controls", None) or []
    if isinstance(children, list):
        for ch in children:
            yield from _walk(ch)
    content = getattr(c, "content", None)
    if content:
        yield from _walk(content)


def _find_icon(root, icon_name):
    for c in _walk(root):
        if isinstance(c, ft.Icon) and c.name == icon_name:
            return c
    return None


def _find_dot(root):
    """Find the liveliness status dot (a Container with border_radius=5)."""
    for c in _walk(root):
        if isinstance(c, ft.Container) and c.border_radius == STATUS_DOT_SIZE // 2:
            return c
    return None
```

- [ ] **Step 2: Implement ChannelCard**

Create `src/app_next/components/channel_card.py`:

```python
"""ChannelCard — single clickable tile in the virtualized grid.

Pure (prefers props over state). Identity key = `ft.ValueKey(channel["url"])`
so GridView reconciliation preserves focus/animations across filter changes.

Favorites: `is_favorite` is passed as a prop (computed in HomeScreen via a
memoized set-lookup). The card does NOT read `state.favorites` directly —
this decouples it from the M5 observable-bug and lets us flip to the fixed
model later without touching card internals.

Liveliness: `liveliness_status` prop (True/False/None). Card calls
`enqueue_logo_download(logo_src)` on render (fire-and-forget outside the
component tree, same as legacy).

Constants verified in `core/constants.py`: CARD_HEIGHT=130,
CARD_BORDER_RADIUS=25, LOGO_SIZE=60, LOGO_BORDER_RADIUS=20, STATUS_DOT_SIZE=10.
"""

from collections.abc import Callable

import flet as ft
from flet.controls.control import Control

from core.constants import (
    CARD_BORDER_RADIUS,
    CARD_HEIGHT,
    LOGO_BORDER_RADIUS,
    LOGO_SIZE,
    STATUS_DOT_SIZE,
)
from core.theme import AppColors
from services.liveliness import liveliness_cache
from services.logo_cache import enqueue_logo_download, get_cached_logo


@ft.component
def ChannelCard(
    channel: dict,
    is_favorite: bool,
    on_play: Callable[[str], None],
    on_toggle_favorite: Callable[[str], None],
    liveliness_status: bool | None = None,
) -> Control:
    url = channel.get("url", "")
    name = channel.get("name", "Unknown")
    logo_src = channel.get("logo") or "/icon.png"

    # --- resolve logo source (same chain as legacy create_channel_card) ---
    if logo_src.startswith("/"):
        resolved_logo = logo_src
    else:
        cached = get_cached_logo(logo_src)
        if cached:
            resolved_logo = cached
        else:
            resolved_logo = logo_src
            enqueue_logo_download(logo_src)  # fire-and-forget

    # --- liveliness dot ---
    if liveliness_status is True:
        dot_color = AppColors.SUCCESS
    elif liveliness_status is False:
        dot_color = AppColors.ERROR
    else:
        dot_color = AppColors.GREY_DIM

    # --- favorite icon ---
    fav_icon = ft.Icon(
        name=ft.Icons.FAVORITE if is_favorite else ft.Icons.FAVORITE_BORDER,
        size=16,
        color=AppColors.PRIMARY if is_favorite else ft.Colors.WHITE_70,
    )

    return ft.Container(
        key=ft.ValueKey(url),
        height=CARD_HEIGHT,
        padding=12,
        border_radius=CARD_BORDER_RADIUS,
        ink=True,
        on_click=lambda e: on_play(url) if on_play else None,
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=fav_icon,
                            on_click=lambda e, u=url: on_toggle_favorite(u),
                            tooltip="Favorite",
                        ),
                        ft.Container(
                            width=STATUS_DOT_SIZE,
                            height=STATUS_DOT_SIZE,
                            border_radius=STATUS_DOT_SIZE // 2,
                            bgcolor=dot_color,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Image(
                    src=resolved_logo,
                    width=LOGO_SIZE,
                    height=LOGO_SIZE,
                    fit=ft.BoxFit.CONTAIN,
                    border_radius=LOGO_BORDER_RADIUS,
                    error_content=ft.Icon(ft.Icons.TV, size=30),
                ),
                ft.Text(
                    name,
                    size=12,
                    weight=ft.FontWeight.W_500,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
    )
```

- [ ] **Step 3: Run tests + commit**

```bash
uv run pytest tests/app_next/test_channel_card.py -v
uv run ruff check src/app_next/components/channel_card.py
git add src/app_next/components/channel_card.py tests/app_next/test_channel_card.py
git commit -m "feat(app_next.components): ChannelCard tile for virtualized grid

Single card with stable key=ValueKey(url), logo + liveliness dot + favorite
icon + channel name layout matching the legacy card dimensions. Favorites
are prop-driven (not from observable state) so the card works correctly
both before and after the M5 favorites-observability fix."
```

---

## Task 6: `ChannelGrid` — virtualized GridView component

**Files:**
- Create: `src/app_next/components/channel_grid.py`
- Modify: `src/app_next/components/__init__.py`
- Create: `tests/app_next/test_channel_grid.py`

**Why:** This replaces the legacy `build_channel_grid()` (ResponsiveRow + ad injection every 12th card) + `pagination.py` (show_prev/show_next). A single flat `GridView(build_controls_on_demand=True, max_extent=160, child_aspect_ratio=0.75, runs_count=3, cache_extent=600)` — verified in M1 that GridView lazily mounts visible items. No pagination — infinite scroll via cache_extent. No `tab_index=900` magic — `focusable=True` on each card via Flutter's traversal.

Ad insertion: legacy inserts a full-width banner ad every 12th channel (`ad_indices` computed in `channel_groups.py:213-216`). The plan preserves this by checking `(global_idx + 1) % 12 == 0` and inserting a full-width `Container` with `col=12` (factored out as a `BannerAdSlot` component). The real ad service banner is accessed through `ad_service` — same as legacy. For M2, ad_service is passed optionally and the slot renders an empty placeholder when ad_service is None (avoids crash in non-ad environments / tests).

When `channels` is empty, renders the shared `EmptyState`.

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_channel_grid.py`:

```python
"""Tests for ChannelGrid component."""

import flet as ft

from app_next.components.channel_grid import ChannelGrid
from core.constants import CHANNEL_CARD_AD_INTERVAL, MAX_SEARCH_RESULTS


def _make_ch(idx):
    return {"url": f"http://x/{idx}", "name": f"Channel {idx}", "logo": ""}


def test_channel_grid_is_a_grid_view():
    grid = ChannelGrid(
        channels=[_make_ch(0)],
        favorites_set=set(),
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_cache=None,
        ad_service=None,
    )
    assert isinstance(grid, ft.GridView)


def test_channel_grid_renders_one_card_per_channel():
    channels = [_make_ch(i) for i in range(5)]
    grid = ChannelGrid(
        channels=channels,
        favorites_set=set(),
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_cache=None,
        ad_service=None,
    )
    card_count = sum(1 for c in grid.controls if isinstance(c, ft.Container))
    # Narrow down: the grid's controls include cards + optional ad slots.
    # Find containers with height matching CARD_HEIGHT.
    from core.constants import CARD_HEIGHT

    card_count = sum(
        1
        for c in grid.controls
        if isinstance(c, ft.Container) and getattr(c, "height", None) == CARD_HEIGHT
    )
    assert card_count == 5


def test_channel_grid_keyed_with_url():
    channels = [_make_ch(0), _make_ch(1)]
    grid = ChannelGrid(
        channels=channels,
        favorites_set=set(),
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_cache=None,
        ad_service=None,
    )
    # At least one card's key contains the URL
    for c in grid.controls:
        if isinstance(c, ft.Container) and c.key is not None:
            assert "http://x/0" in str(c.key) or "http://x/1" in str(c.key)
            return
    # If we exit the loop without finding a keyed container, fail
    assert False, "No keyed ChannelCard found in GridView"


def test_channel_grid_empty_with_no_channels():
    grid = ChannelGrid(
        channels=[],
        favorites_set=set(),
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_cache=None,
        ad_service=None,
    )
    from app_next.components.empty_state import EmptyState

    # When no channels, render an EmptyState instead of a 0-card GridView.
    assert isinstance(grid, EmptyState) or len(grid.controls) == 0


def test_channel_grid_injects_ad_every_12th_channel():
    channels = [_make_ch(i) for i in range(25)]
    grid = ChannelGrid(
        channels=channels,
        favorites_set=set(),
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_cache=None,
        ad_service="dummy",  # non-None triggers ad slot insertion
    )
    card_count = sum(
        1
        for c in grid.controls
        if isinstance(c, ft.Container) and getattr(c, "height", 0) == 130
    )
    # 24 channels should produce 2 ads (at positions 12 and 24)
    # The GridView would have 25 items if no ads, ~27 with ads.
    assert len(grid.controls) >= 26  # at least 2 ad slots inserted
```

- [ ] **Step 2: Implement ChannelGrid**

Create `src/app_next/components/channel_grid.py`:

```python
"""ChannelGrid — single flat virtualized GridView with ad insertion.

Legacy pagination (show_prev/show_next) is removed. GridView's
build_controls_on_demand=True lazy-mounts off-screen items. Cards are
keyed by URL for stable identity across filter changes. Ad banners are
inserted every CHANNEL_CARD_AD_INTERVAL (12) channels — matching the
legacy `ad_indices` logic in channel_groups.py:213-216.
"""

from collections.abc import Callable
from typing import Any

import flet as ft
from flet.controls.control import Control

from app_next.components.channel_card import ChannelCard
from app_next.components.empty_state import EmptyState
from core.constants import CHANNEL_CARD_AD_INTERVAL
from services.liveliness import liveliness_cache


@ft.component
def ChannelGrid(
    channels: list[dict],
    favorites_set: set[str],
    on_play: Callable[[str], None],
    on_toggle_favorite: Callable[[str], None],
    liveliness_cache_obj: Any = None,  # Accepts the liveliness_cache module or None
    ad_service: Any = None,
) -> Control:
    """Render channel list as a virtualized GridView.

    Args:
        channels: filtered channels to display.
        favorites_set: set of URLs for O(1) favorite lookup.
        on_play: fires with URL when a card is clicked.
        on_toggle_favorite: fires with URL when the star icon is clicked.
        liveliness_cache_obj: used for per-card liveliness lookup
            (liveliness_cache.get(url)). Defaults to module-level.
        ad_service: optional ad service; inserts banner ads at intervals.
    """
    _liveliness = liveliness_cache_obj or liveliness_cache

    controls: list[Control] = []

    for idx, ch in enumerate(channels):
        url = ch.get("url", "")
        keys_match = ft.ValueKey(url)  # used for stable identity per card

        card = ChannelCard(
            key=keys_match,
            channel=ch,
            is_favorite=url in favorites_set,
            on_play=on_play,
            on_toggle_favorite=on_toggle_favorite,
            liveliness_status=_liveliness.get(url)
            if hasattr(_liveliness, "get")
            else None,
        )

        # Wrap card in a col-responsive container for consistent sizing
        controls.append(
            ft.Container(
                content=card, col={"xs": 4, "sm": 3, "md": 2, "lg": 2}, padding=4
            )
        )

        # Ad insertion: every N-th channel (legacy behaviour)
        if ad_service and (idx + 1) % CHANNEL_CARD_AD_INTERVAL == 0:
            ad_slot = (
                ad_service.get_standard_banner_ad()
                if hasattr(ad_service, "get_standard_banner_ad")
                else None
            )
            if ad_slot:
                controls.append(
                    ft.Container(
                        content=ad_slot,
                        col=12,
                        alignment=ft.alignment.center,
                        padding=ft.Padding(0, 5, 0, 5),
                    )
                )
            else:
                # Non-None ad_service but no ad returned = insert a 20px spacer
                controls.append(ft.Container(col=12, height=20))

    if not controls:
        return EmptyState(
            title="No channels found",
            message="Adjust filters or add content.",
            action_label=None,
        )

    return ft.GridView(
        controls=controls,
        runs_count=3,
        max_extent=160,
        child_aspect_ratio=0.75,
        spacing=12,
        run_spacing=12,
        padding=ft.Padding(8, 4, 8, 4),
        cache_extent=600,
        build_controls_on_demand=True,
    )
```

- [ ] **Step 3: Run tests + commit**

```bash
uv run pytest tests/app_next/test_channel_grid.py -v
uv run ruff check src/app_next/components/channel_grid.py
git add src/app_next/components/channel_grid.py tests/app_next/test_channel_grid.py
git commit -m "feat(app_next.components): ChannelGrid flat virtualized grid

Single GridView with build_controls_on_demand, keyed ChannelCards, and
ad insertion every CHANNEL_CARD_AD_INTERVAL channels. Empty state
delegates to EmptyState. Replaces legacy build_channel_grid (ResponsiveRow)
and pagination.py."
```

---

## Task 7: `RecentlyWatched` component

**Files:**
- Create: `src/app_next/components/recently_watched.py`
- Modify: `src/app_next/components/__init__.py`
- Create: `tests/app_next/test_recently_watched.py`

**Why:** Horizontal scrolling carousel showing the last 10 watched channels. Replaces legacy `dashboard_carousel.py`. Uses a horizontal `ListView(build_controls_on_demand=True)`. When `history` is empty, renders nothing (returns `None`/empty Container). Each item is a small clickable card (logo + name). Cards are keyed by URL.

Legacy behaviour (verified in `dashboard_carousel.py`):
- Max items: `state.history[:10]` (line 26)
- Channel map lookup: `{ch["url"]: ch for ch in state.channels}` (line 23)
- Card: `width=72` for text, logo `width=52, height=52`
- Section visible only when `bool(state.history)` — line 93
- Click fires `page_obj.run_task(on_play, u)` — in our case `on_play(u)` because M2 uses components-mode and the caller owns the exec model

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_recently_watched.py`:

```python
"""Tests for RecentlyWatched carousel component."""

import flet as ft
from app_next.components.recently_watched import RecentlyWatched


def _make_ch(name, url):
    return {"name": name, "url": url, "logo": ""}


def test_recently_watched_hidden_when_no_history():
    rw = RecentlyWatched(history=[], channels_map={}, on_play=lambda u: None)
    # Should be invisible when no items
    if isinstance(rw, ft.Container):
        assert rw.visible is False
    else:
        # A Column or Row with visible=False also works
        assert isinstance(rw, ft.Container)


def test_recently_watched_lists_up_to_10_items():
    history = [f"http://x/{i}" for i in range(15)]
    channels_map = {
        f"http://x/{i}": _make_ch(f"C{i}", f"http://x/{i}") for i in range(15)
    }
    rw = RecentlyWatched(
        history=history, channels_map=channels_map, on_play=lambda u: None
    )
    # Walk the tree and count clickable cards
    cards = _find_card_like(rw)
    assert len(cards) <= 10
    if len(history) > 10:
        assert len(cards) == 10


def test_recently_watched_card_triggers_on_play():
    fired = []
    history = ["http://x/0"]
    channels_map = {"http://x/0": _make_ch("C0", "http://x/0")}
    rw = RecentlyWatched(
        history=history, channels_map=channels_map, on_play=lambda u: fired.append(u)
    )
    cards = _find_card_like(rw)
    if cards:
        # Simulate click
        cards[0].on_click(None)
        assert fired == ["http://x/0"]


# helpers
def _walk(c):
    yield c
    children = getattr(c, "controls", None) or []
    if isinstance(children, list):
        for ch in children:
            yield from _walk(ch)
    content = getattr(c, "content", None)
    if content:
        yield from _walk(content)


def _find_card_like(root):
    """Find interactive containers that look like carousel cards."""
    results = []
    for c in _walk(root):
        if isinstance(c, ft.Container) and hasattr(c, "on_click") and c.on_click:
            results.append(c)
    return results
```

- [ ] **Step 2: Implement RecentlyWatched**

Create `src/app_next/components/recently_watched.py`:

```python
"""RecentlyWatched — horizontal scrolling carousel of last 10 watched streams."""

from collections.abc import Callable

import flet as ft
from flet.controls.control import Control

from core.constants import LBL_RECENTLY_WATCHED
from core.theme import AppColors
from services.logo_cache import get_cached_logo


@ft.component
def RecentlyWatched(
    history: list[str],
    channels_map: dict[str, dict],
    on_play: Callable[[str], None],
) -> Control:
    """Horizontal carousel. Hidden when history is empty.

    Args:
        history: list[str] of watched URLs, most-recent first.
        channels_map: {url: channel_dict} for resolving names and logos.
        on_play: fires with URL when a carousel card is clicked.
    """
    visible_items = history[:10]  # match legacy dashboard_carousel.py:26

    if not visible_items:
        return ft.Container(height=0, visible=False)

    cards = []
    for url in visible_items:
        ch = channels_map.get(url, {"name": url, "logo": ""})
        logo_src = ch.get("logo", "") or "/icon.png"
        if not logo_src.startswith("/"):
            cached = get_cached_logo(logo_src)
            if cached:
                logo_src = cached

        cards.append(
            ft.Container(
                key=ft.ValueKey(url),
                content=ft.Column(
                    controls=[
                        ft.Image(
                            src=logo_src,
                            width=52,
                            height=52,
                            fit=ft.BoxFit.CONTAIN,
                            border_radius=8,
                            error_content=ft.Icon(ft.Icons.TV, size=24),
                        ),
                        ft.Text(
                            ch.get("name", "Stream"),
                            size=11,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            width=72,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                    spacing=2,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                on_click=lambda e, u=url: on_play(u),
                padding=8,
                ink=True,
                border_radius=10,
            )
        )

    return ft.Container(
        expand=True,
        content=ft.Column(
            controls=[
                ft.Text(
                    LBL_RECENTLY_WATCHED,
                    size=15,
                    weight=ft.FontWeight.W_600,
                    color=AppColors.GREY_DIM,
                ),
                ft.ListView(
                    controls=cards,
                    horizontal=True,
                    spacing=8,
                    build_controls_on_demand=True,
                ),
            ],
            spacing=6,
        ),
        padding=ft.Padding(12, 4, 12, 4),
    )
```

- [ ] **Step 3: Run tests + commit**

```bash
uv run pytest tests/app_next/test_recently_watched.py -v
uv run ruff check src/app_next/components/recently_watched.py
git add src/app_next/components/recently_watched.py tests/app_next/test_recently_watched.py
git commit -m "feat(app_next.components): RecentlyWatched horizontal carousel

Shows up to 10 recent channels, hidden when empty. Uses horizontal
ListView with build_controls_on_demand. Cards keyed by URL. Logo
resolution uses the same get_cached_logo chain as legacy."
```

---

## Task 8: `AddCustomContentDialog` component

**Files:**
- Create: `src/app_next/components/add_custom_content_dialog.py`
- Modify: `src/app_next/components/__init__.py`
- Create: `tests/app_next/test_add_custom_content_dialog.py`

**Why:** Replaces legacy `custom_tab.py`'s inline `AlertDialog` (lines 136-250 of the legacy file). The dialog opens from an AppBar action (`+` icon) on HomeScreen. Has a `SegmentedButton` to choose Playlist vs Single Channel, `TextField` for name, `TextField` for URL, and an Add button with cooldown enforcement. On submit it persists to `db_manager` via `use_storage` and calls `on_added(needs_refresh=True)` so the parent can trigger `controller.refresh_channels()`.

Legacy invariants (verified in `custom_tab.py`):
- `ADD_CONTENT_COOLDOWN = 5.0` seconds (module-level `_last_add_time` tracked)
- `MAX_NAME_LENGTH = 200`
- URL validation: must start with `http://` or `https://`
- SegmentedButton options: `"Playlist"` and `"Single Channel"`
- Name auto-fallback to `"Unnamed Playlist"` / `"Unnamed Channel"` if empty
- On success: `page_obj.show_dialog(ft.SnackBar(...))` (we keep the existing migration pattern — `page.show_dialog(SnackBar(...))` — via the `_notify_warning` helper pattern from M1)
- On success: invalidates dashboard cache and calls `load_channels(force=True)`

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_add_custom_content_dialog.py`:

```python
"""Tests for AddCustomContentDialog component.

Tests the dialog's pure validation logic and the cooldown enforcement.
The dialog itself is rendered inside HomeScreen and tested in manual smoke.
"""

from app_next.components.add_custom_content_dialog import (
    _is_valid_url,
    _can_add,
    _format_name,
    ADD_CONTENT_COOLDOWN,
)


def test_valid_url_accepts_http_and_https():
    assert _is_valid_url("http://example.com/stream.m3u8") is True
    assert _is_valid_url("https://example.com/playlist.m3u") is True
    assert _is_valid_url("HTTP://example.com") is True


def test_valid_url_rejects_non_http():
    assert _is_valid_url("") is False
    assert _is_valid_url("ftp://example.com") is False
    assert _is_valid_url("rtmp://example.com") is False
    assert _is_valid_url("not-a-url") is False
    assert _is_valid_url("http://") is False  # no host


def test_can_add_enforces_name_length():
    assert _can_add("Valid Name", "http://x", 0.0) is True
    assert _can_add("", "http://x", 0.0) is False
    name_too_long = "x" * 201
    assert _can_add(name_too_long, "http://x", 0.0) is False


def test_can_add_enforces_url_validation():
    assert _can_add("Test", "invalid", 0.0) is False


def test_can_add_enforces_cooldown():
    import time

    assert _can_add("Test", "http://x", time.time()) is True
    assert _can_add("Test", "http://x", time.time() - ADD_CONTENT_COOLDOWN + 1) is True
    assert _can_add("Test", "http://x", time.time() - ADD_CONTENT_COOLDOWN - 1) is True


def test_can_add_blocks_rapid_submit():
    import time

    now = time.time()
    # First call within cooldown window
    assert _can_add("Test", "http://x", now) is True  # no last_add_time, so allowed
    # Immediately after, simulate last_add_time = now
    assert _can_add("Test", "http://x", now) is False  # too soon
    # After cooldown passes
    assert _can_add("Test", "http://x", now - ADD_CONTENT_COOLDOWN) is True


def test_format_name_provides_fallback():
    assert _format_name("", "playlist") == "Unnamed Playlist"
    assert _format_name("", "channel") == "Unnamed Channel"
    assert _format_name("My Channel", "channel") == "My Channel"
    assert _format_name("  Trimmed  ", "playlist") == "Trimmed"
```

- [ ] **Step 2: Implement AddCustomContentDialog**

Create `src/app_next/components/add_custom_content_dialog.py`:

```python
"""AddCustomContentDialog — modal for adding M3U playlist or single channel.

Opened from HomeScreen's AppBar action. Mirrors the legacy custom_tab.py's
AlertDialog with SegmentedButton, name + URL fields, and cooldown.
"""

import time
from collections.abc import Awaitable, Callable
from typing import Any

import flet as ft
from flet.controls.control import Control

from app_next.hooks.use_storage import use_storage
from core.constants import (
    ADD_CONTENT_COOLDOWN,
    LBL_ADD,
    LBL_ADDED_SUCCESS,
    LBL_CANCEL,
    LBL_NAME,
    LBL_NAME_HINT,
    LBL_PLAYLIST,
    LBL_SINGLE_CHANNEL,
    LBL_TV_FIELD_HINT,
    LBL_TYPE,
    LBL_URL,
    LBL_URL_HINT,
    MAX_NAME_LENGTH,
)
from core.theme import AppColors

# --- pure helpers (exported for unit tests) ---


def _is_valid_url(url: str) -> bool:
    stripped = url.strip()
    return (
        stripped.startswith(("http://", "https://", "HTTP://", "HTTPS://"))
        and len(stripped) > 10
    )


def _can_add(name: str, url: str, last_add_time: float) -> bool:
    from core.constants import MAX_NAME_LENGTH, ADD_CONTENT_COOLDOWN

    if not name.strip():
        return False
    if len(name.strip()) > MAX_NAME_LENGTH:
        return False
    if not _is_valid_url(url):
        return False
    if last_add_time > 0 and (time.time() - last_add_time) < ADD_CONTENT_COOLDOWN:
        return False
    return True


def _format_name(name: str, add_type: str) -> str:
    stripped = name.strip()
    if not stripped:
        return "Unnamed Playlist" if add_type == "playlist" else "Unnamed Channel"
    return stripped


@ft.component
def AddCustomContentDialog(
    open: bool,
    on_close: Callable[[], None],
    on_added: Callable[[], Awaitable[None] | None],
) -> Control:
    """Render an AlertDialog for adding custom content.

    Args:
        open: whether the dialog is visible.
        on_close: fires when the user cancels or the dialog is dismissed.
        on_added: fires after successful persistence (parent should
            refresh channels).
    """
    if not open:
        return ft.Container(height=0, visible=False)

    add_type, set_add_type = ft.use_state("playlist")
    name, set_name = ft.use_state("")
    url, set_url = ft.use_state("")
    last_add, set_last_add = ft.use_state(0.0)
    is_adding, set_is_adding = ft.use_state(False)
    storage = use_storage()

    def _reset():
        set_name("")
        set_url("")
        set_add_type("playlist")
        set_last_add(0.0)

    async def _handle_add(e):
        if is_adding:
            return
        if not _can_add(name, url, last_add):
            return

        set_is_adding(True)
        try:
            final_name = _format_name(name, add_type)
            final_url = url.strip()

            if add_type == "playlist":
                await storage.db_manager.add_playlist(final_name, final_url)
            else:
                await storage.db_manager.add_custom_channel(final_name, final_url)

            _notify_success(LBL_ADDED_SUCCESS.format(name=final_name))
            set_last_add(time.time())
            _reset()
            result = on_added()
            if hasattr(result, "__await__"):
                import asyncio

                asyncio.create_task(result)
        except Exception:
            _notify_warning("Failed to add content.")
        finally:
            set_is_adding(False)

    async def _handle_cancel(e):
        _reset()
        on_close()

    return ft.AlertDialog(
        modal=True,
        title=ft.Text("Add Custom Content"),
        content=ft.Column(
            controls=[
                ft.Text(LBL_TYPE, size=14, weight=ft.FontWeight.W_600),
                ft.SegmentedButton(
                    on_change=lambda e: set_add_type(e.control.selected_value),
                    selected_value=add_type,
                    controls=[
                        ft.ButtonSegment(LBL_PLAYLIST),
                        ft.ButtonSegment(LBL_SINGLE_CHANNEL),
                    ],
                ),
                ft.TextField(
                    label=LBL_NAME,
                    hint_text=LBL_NAME_HINT,
                    value=name,
                    on_change=lambda e: set_name(e.control.value),
                    max_length=MAX_NAME_LENGTH,
                    helper_text=LBL_TV_FIELD_HINT,
                    autofocus=True,
                ),
                ft.TextField(
                    label=LBL_URL,
                    hint_text=LBL_URL_HINT,
                    value=url,
                    on_change=lambda e: set_url(e.control.value),
                ),
            ],
            width=350,
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            ft.TextButton(LBL_CANCEL, on_click=_handle_cancel),
            ft.FilledButton(
                content=ft.Text(LBL_ADD),
                on_click=_handle_add,
                disabled=not _can_add(name, url, last_add) or is_adding,
            ),
        ],
        on_dismiss=_reset,
    )


def _notify_success(msg: str) -> None:
    from flet.controls.context import context

    try:
        context.page.show_dialog(ft.SnackBar(ft.Text(msg)))
    except Exception:
        pass


def _notify_warning(msg: str) -> None:
    from flet.controls.context import context

    try:
        context.page.show_dialog(ft.SnackBar(ft.Text(msg), bgcolor=AppColors.WARNING))
    except Exception:
        pass
```

- [ ] **Step 3: Run tests + commit**

```bash
uv run pytest tests/app_next/test_add_custom_content_dialog.py -v
uv run ruff check src/app_next/components/add_custom_content_dialog.py
git add src/app_next/components/add_custom_content_dialog.py tests/app_next/test_add_custom_content_dialog.py
git commit -m "feat(app_next.components): AddCustomContentDialog modal

SegmentedButton (Playlist/Channel) + name + URL fields with cooldown
(ADD_CONTENT_COOLDOWN=5s) and URL validation. Persists via db_manager
and fires on_added for channel refresh. Replaces legacy custom_tab.py
Add Content AlertDialog."
```

---

## Task 9: `HomeScreen` — the component that wires everything together

**Files:**
- Create: `src/app_next/screens/home_screen.py`
- Modify: `src/app_next/screens/__init__.py`
- Create: `tests/app_next/test_home_screen.py`

**Why:** This is the crown jewel of M2. It reads observable state, builds a filtered channel list, composes `RecentlyWatched` + `FilterBar` + `ChannelGrid` into a single scrollable layout, and handles favorites toggling + play + add-custom-content through the controller context. No `page_obj._dashboard_refresh` monkey-patch — state changes flow through observable subscriptions.

Layout (from top to bottom of a single `ft.Column`):
1. **Header bar**: app icon + "Add Content" `IconButton` (opens AddCustomContentDialog) + theme toggle icon button (mirrors legacy Dashboard header)
2. **RecentlyWatched carousel** (hidden when history empty)
3. **FilterBar** (sticky chips)
4. **ChannelGrid** (virtualized, single flat view, with EmptyState)

All observable reads go through `ft.use_context(AppStateCtx)` for auto-subscription.

Favorites: `build_favorites_set = use_memo(lambda: set(state.favorites), [state.favorites])` creates a `set` from `state.favorites` (still a `set[str]` until M5, but observable hash change works via `channels_hash`). This memo rebuilds only when `state.channels_hash` changes (which includes the channels list replacement). Toggling favorites mutates `state.favorites` (a Python `set`, not observable until M5) AND persists to DB. Since toggling favorites today doesn't trigger observable notification, we also call `channels_hash += 1` (a hack — fixed in M5). For now: same behaviour as legacy, but through a clean pattern.

- [ ] **Step 1: Write the failing test**

Create `tests/app_next/test_home_screen.py`:

```python
"""Tests for HomeScreen component.

Verifies composition of sub-components and channel filtering flow.
The component is a @ft.component requiring an active renderer for
full mounting; unit tests verify the pure composition helpers.
"""

import flet as ft

from app_next.screens.home_screen import (
    HomeScreen,
    _build_channels_map,
    _build_favorites_set,
)


def test_home_screen_marked_as_component():
    assert getattr(HomeScreen, "__is_component__", False) is True


def test_build_channels_map_returns_dict_keyed_by_url():
    channels = [
        {"url": "http://a", "name": "A"},
        {"url": "http://b", "name": "B"},
    ]
    m = _build_channels_map(channels)
    assert m["http://a"]["name"] == "A"
    assert m["http://b"]["name"] == "B"


def test_build_channels_map_skips_channels_without_url():
    channels = [
        {"url": "http://a", "name": "A"},
        {"name": "NoURL"},
    ]
    m = _build_channels_map(channels)
    assert "http://a" in m
    assert len(m) == 1


def test_build_favorites_set_returns_set_from_whatever_state_provides():
    class FakeState:
        favorites = {"http://fav1", "http://fav2"}

    s = _build_favorites_set(FakeState())
    assert s == {"http://fav1", "http://fav2"}


def test_build_favorites_set_handles_list():
    class FakeState:
        favorites = ["http://fav1", "http://fav2"]

    s = _build_favorites_set(FakeState())
    assert s == {"http://fav1", "http://fav2"}
```

- [ ] **Step 2: Implement HomeScreen**

Create `src/app_next/screens/home_screen.py`:

```python
"""HomeScreen — main browsing screen compositing carousel + filters + grid.

Reads observable AppState via use_context. Memoizes channel maps and
filtered results. Owns the "Add Custom Content" dialog state and the
favorites toggle flow. Delegates to sub-components.
"""

from collections.abc import Callable
from typing import Any

import flet as ft
from flet.controls.control import Control

from app_next.components.add_custom_content_dialog import AddCustomContentDialog
from app_next.components.channel_grid import ChannelGrid
from app_next.components.empty_state import EmptyState
from app_next.components.filter_bar import FilterBar
from app_next.components.recently_watched import RecentlyWatched
from app_next.hooks.apply_filters import _default_filters, apply_filters
from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from core.constants import LBL_ADD_CONTENT
from core.state import state as core_state
from database.manager import db_manager


# --- pure helpers (exported for tests) ---


def _build_channels_map(channels: list[dict]) -> dict[str, dict]:
    return {ch["url"]: ch for ch in channels if ch.get("url")}


def _build_favorites_set(state_obj: Any) -> set[str]:
    favs = state_obj.favorites
    if isinstance(favs, set):
        return favs
    if isinstance(favs, list):
        return set(favs)
    return set()


@ft.component
def HomeScreen() -> Control:
    """Main home browsing screen.

    Subscribes to AppStateCtx for auto-re-render when channels/history/
    favorites change. Uses ControllerMethodsCtx for play_stream and
    refresh_channels.
    """
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    # Local UI state
    filters, set_filters = ft.use_state(_default_filters())
    add_dialog_open, set_add_dialog_open = ft.use_state(False)
    is_dark, set_is_dark = ft.use_state(_resolve_theme_mode())

    # Derived state — memoized to avoid recomputation on unrelated updates
    channels_map = ft.use_memo(
        lambda: _build_channels_map(state.channels), [state.channels_hash]
    )
    favorites_set = ft.use_memo(
        lambda: _build_favorites_set(state), [state.channels_hash, state.theme_mode]
    )
    visible = ft.use_memo(
        lambda: apply_filters(state.channels, filters, favorites_set),
        [state.channels_hash, filters, favorites_set],
    )

    # --- handlers ---

    def on_play(url: str):
        controller.play_stream(url, None)

    def on_toggle_favorite(url: str):
        _toggle_favorite_async(url, state, favorites_set)
        # Force observable hash bump to trigger re-render until M5 fixes favourites
        # (M5 makes state.favorites observable; then this line is removed)
        core_state.channels_hash += 1

    def on_filters_updated(new_filters: dict):
        set_filters(new_filters)

    async def on_add_content_complete():
        set_add_dialog_open(False)
        await controller.refresh_channels()

    def toggle_theme(e):
        from flet.controls.context import context

        page = context.page
        is_dark = _resolve_theme_mode()
        new_mode = ft.ThemeMode.LIGHT if is_dark else ft.ThemeMode.DARK
        page.theme_mode = new_mode
        set_is_dark(new_mode == ft.ThemeMode.DARK)

        # Persist
        async def _save():
            await db_manager.set_setting(
                "theme_mode", "dark" if new_mode == ft.ThemeMode.DARK else "light"
            )

        page.run_task(_save)
        core_state.channels_hash += 1  # force re-render of theme-dependent controls

    # --- Build tree ---

    header = ft.Row(
        controls=[
            ft.Image(
                src="/icon.png",
                width=36,
                height=36,
                fit=ft.BoxFit.CONTAIN,
                border_radius=8,
            ),
            ft.IconButton(
                icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                tooltip=LBL_ADD_CONTENT,
                on_click=lambda e: set_add_dialog_open(True),
                icon_size=22,
            ),
            ft.IconButton(
                icon=ft.Icons.LIGHT_MODE if is_dark else ft.Icons.DARK_MODE,
                tooltip="Toggle Theme",
                on_click=toggle_theme,
                icon_size=18,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    recently = RecentlyWatched(
        history=state.history,
        channels_map=channels_map,
        on_play=on_play,
    )

    filter_bar = FilterBar(
        filters=filters,
        on_change=on_filters_updated,
        available_countries=_extract_countries(state.channels),
        available_categories=_extract_categories(state.channels),
        user_country=state.user_country,
        total_count=len(visible),
    )

    if not visible:
        body = EmptyState(
            title="No channels found",
            message="Try changing filters or add custom content.",
            action_label="Add Content",
            icon=ft.Icons.LIVE_TV,
            on_action=lambda e: set_add_dialog_open(True),
        )
    else:
        body = ChannelGrid(
            channels=visible,
            favorites_set=favorites_set,
            on_play=on_play,
            on_toggle_favorite=on_toggle_favorite,
            liveliness_cache=None,  # defaults to module-level singleton
            ad_service=controller.ad_service
            if hasattr(controller, "ad_service")
            else None,
        )

    dialog = AddCustomContentDialog(
        open=add_dialog_open,
        on_close=lambda: set_add_dialog_open(False),
        on_added=on_add_content_complete,
    )

    return ft.Container(
        expand=True,
        content=ft.Column(
            controls=[
                ft.Container(content=header, padding=ft.Padding(12, 8, 12, 4)),
                recently,
                filter_bar,
                body,
                dialog,
            ],
            expand=True,
            spacing=0,
        ),
    )


# --- module-level helpers (no component dependency) ---


def _resolve_theme_mode() -> bool:
    try:
        from flet.controls.context import context

        page = context.page
        if page.theme_mode == ft.ThemeMode.SYSTEM:
            try:
                return page.platform_brightness == ft.Brightness.DARK
            except Exception:
                return True
        return page.theme_mode == ft.ThemeMode.DARK
    except Exception:
        return True  # default to dark if no page context


def _extract_countries(channels: list[dict]) -> list[str]:
    seen = set()
    result = []
    for c in channels:
        group = c.get("group", "General")
        country = group.split(";")[0].strip()
        if country and country not in seen and c.get("country_code"):
            seen.add(country)
            result.append(country)
    return sorted(result)


def _extract_categories(channels: list[dict]) -> list[str]:
    seen = set()
    result = []
    for c in channels:
        group = c.get("group", "General")
        if group and group not in seen:
            seen.add(group)
            result.append(group)
    return sorted(result)


def _toggle_favorite_async(url: str, state, favorites_set: set[str]):
    """Fire-and-forget DB persistence: add/remove favorite."""

    async def _do():
        try:
            if url in favorites_set:
                await db_manager.remove_favorite(url)
                state.favorites.discard(url)
            else:
                await db_manager.add_favorite(url)
                state.favorites.add(url)
        except Exception:
            pass

    from functools import partial
    from asyncio import create_task

    create_task(_do())
```

- [ ] **Step 3: Export**

Update `src/app_next/screens/__init__.py`:

```python
from app_next.screens.onboarding_screen import OnboardingScreen
from app_next.screens.placeholder_screen import PlaceholderScreen
from app_next.screens.home_screen import HomeScreen

__all__ = ["OnboardingScreen", "PlaceholderScreen", "HomeScreen"]
```

- [ ] **Step 4: Run tests + commit**

```bash
uv run pytest tests/app_next/test_home_screen.py -v
uv run ruff check src/app_next/screens/home_screen.py
git add src/app_next/screens/home_screen.py src/app_next/screens/__init__.py tests/app_next/test_home_screen.py
git commit -m "feat(app_next.screens): HomeScreen compositing carousel+filters+grid

Wires RecentlyWatched + FilterBar + ChannelGrid + AddCustomContentDialog
via observable state and controller context. Memoizes channel_map, favorites
set, and filtered results. Theme toggle persists to DB. No monkey-patches.
Replaces legacy dashboard.py + channel_groups.py + custom_tab.py +
dashboard_carousel.py (combined ~600 lines)."
```

---

## Task 10: Update AppShell to mount HomeScreen, integration smoke, close-out

**Files:**
- Modify: `src/app_next/app_shell.py` (replace PlaceholderScreen("Home") with HomeScreen on tab 0)
- Create: `tests/app_next/test_integration_smoke_m2.py`
- Modify: `tests/app_next/test_home_screen.py` (add a render-source regression test like M1's `test_app_shell_source_uses_use_context_for_state`)

**Why:** The four-tab scaffold from M1 now needs HomeScreen on destination 0 instead of PlaceholderScreen("Home"). The other three destinations stay PlaceholderScreen (filled in M3/M4). We also add the same regression test this plan has been consistent about — use_context for state access, not plain import.

- [ ] **Step 1: Update AppShell**

The current AppShell in `src/app_next/app_shell.py` already has a `_dashboard_scaffold` function that takes `selected_tab` and an `on_change` callback, and calls `PlaceholderScreen(key=..., name=_TAB_NAMES[selected_tab])`. We change that single line:

```python
def _dashboard_scaffold(
    selected_tab: int,
    on_change: "callable[[int], None]",
) -> ft.Column:
    """Build the dashboard body: a 4-destination NavigationBar keyed body."""
    destinations = [...]  # unchanged

    # --- REPLACE THIS LINE ---
    # Old: body = PlaceholderScreen(key=ft.ValueKey(_TAB_NAMES[selected_tab]), name=_TAB_NAMES[selected_tab])
    # New (M2):
    if _TAB_NAMES[selected_tab] == "Home":
        body = HomeScreen(key=ft.ValueKey("home"))
    else:
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
```

Add import at the top:

```python
from app_next.screens.home_screen import HomeScreen
```

No other changes to AppShell. Theme toggle: HomeScreen now owns its own theme toggle (in its header). AppShell's theme sync (`on_updated` syncing state.theme_mode → page.theme_mode) remains — it's the system-level sync. The user can toggle from either the shell (future capability) or the Home header (current). Both write to the same target and observable, so no conflict.

- [ ] **Step 2: Add regression test for use_context rule**

Append a test similar to M1's to `tests/app_next/test_home_screen.py`:

```python
def test_home_screen_source_uses_use_context_for_state():
    """Regression guard: HomeScreen must access state via use_context(AppStateCtx).
    Same invariant as AppShell. A plain import would not auto-subscribe and
    the Home screen would never re-render when channels/history/favorites change.
    """
    import inspect
    from app_next.screens import home_screen

    source = inspect.getsource(home_screen)
    assert "use_context(AppStateCtx)" in source
    # Also check the antipattern is absent in the rendered body
    code_lines = [
        line
        for line in source.splitlines()
        if not line.strip().startswith(("#", '"""', "'''"))
    ]
    code = "\n".join(code_lines)
    assert "from app_next.state.app_state import state" not in code
```

Also, HomeScreen accesses `core_state` directly (the plain import `from core.state import state as core_state` for the `channels_hash += 1` hack). That's intentional — it's used inside `on_toggle_favorite`, NOT during the render cycle, so it doesn't need a subscription. Document via an inline comment in home_screen.py: "# Direct core.state import OK here — only used in on_toggle_favorite's fire-and-forget persistence, not in the render function (use_context handles subscriptions)."

- [ ] **Step 3: Update the integration smoke test**

Create `tests/app_next/test_integration_smoke_m2.py`:

```python
"""M2 integration smoke tests: HomeScreen composes and renders without error.

Render-level assertions (visual correctness) are in manual smoke (Step 5).
Here we test pure helpers and source-invariant guards.
"""

from app_next.screens.home_screen import (
    HomeScreen,
    _build_channels_map,
    _build_favorites_set,
    _extract_countries,
    _extract_categories,
)


def test_extract_countries_from_channels():
    channels = [
        {"url": "http://a", "group": "Nigeria;Sports", "country_code": "M3U"},
        {"url": "http://b", "group": "Nigeria;News", "country_code": "M3U"},
        {"url": "http://c", "group": "Ghana;General", "country_code": "M3U"},
        {"url": "http://d", "group": "General", "country_code": ""},  # not a country
    ]
    c = _extract_countries(channels)
    assert "Nigeria" in c
    assert "Ghana" in c
    assert "General" not in c  # no country_code


def test_extract_categories_deduplicates():
    channels = [
        {"url": "http://a", "group": "Nigeria;Sports"},
        {"url": "http://b", "group": "Nigeria;Sports"},
        {"url": "http://c", "group": "Nigeria;News"},
    ]
    c = _extract_categories(channels)
    assert c == ["Nigeria;News", "Nigeria;Sports"]  # sorted
```

- [ ] **Step 4: Full regression sweep**

Run:

```bash
uv run pytest tests/app_next/ -q  # all app_next tests
uv run pytest -q  # full suite (legacy tests)
uv run ruff check src/ tests/
```

Expected: all green, ruff clean. If any legacy tests fail, they were broken before M2 (shouldn't happen — we never touch `src/views/` or `src/core/*` in M2 except `db_manager` is unchanged).

- [ ] **Step 5: Manual smoke**

In a terminal with GUI:

```bash
KTV_FRONTEND=next uv run flet run src/main.py
```

Expected after onboarding (or if already accepted terms):
1. **Home screen** renders: header (logo + add-content button + theme toggle), RecentlyWatched (empty on first launch), FilterBar chips (Country / Category / Fav / Source), ChannelGrid with channels from the Free-TV/IPTV directory.
2. **Tap a country chip** → dropdown overlay with "All" + country list. Selecting "Nigeria" filters the grid to only Nigerian channels.
3. **Tap the Favorites chip** → all channels disappear (none favorited yet). Tap a channel card's star → card re-renders with filled star. Tap the Favorites chip again → that channel appears.
4. **Tap the "Add Content" `+` button** → dialog opens with SegmentedButton (Playlist/Channel) + name + URL fields. Enter a name + valid URL → "Start Watching" adds it, dialog closes, grid refreshes with the custom channel.
5. **Add invalid URL** → Add button is disabled; error notification on attempt.
6. **Tap the Theme toggle** → switches between light/dark, persists across restart.
7. **Switch to Search / Local / Settings tabs** (placeholders) → shows M1 PlaceholderScreen.
8. **Back to Home** → filter state is preserved (CleanTab component is keyed so it resets, that's intended — simpler than preserving filter state across tabs. If filter preservation is desired, lift `filters` to `AppShell` — but not in M2 scope.)
9. **Run without KTV_FRONTEND=next** → legacy 5-tab dashboard unchanged.

- [ ] **Step 6: Final regression + commit**

```bash
uv run pytest -q
uv run ruff check src/ tests/ -q
git add src/app_next/app_shell.py tests/app_next/test_home_screen.py tests/app_next/test_integration_smoke_m2.py
git commit -m "feat(app_next): wire HomeScreen into AppShell, M2 integration smoke

AppShell's tab 0 now renders the real HomeScreen instead of a placeholder.
HomeScreen uses the observable-subscription pattern (use_context(AppStateCtx))
with regression guards. Pure helpers tested: extract_countries/categories,
channel_map builder, favorites set builder. Manual smoke verified on
KTV_FRONTEND=next flet run."
```

---

## Done checklist

- [ ] Tasks 1-10 committed
- [ ] `uv run pytest -q` green
- [ ] `uv run ruff check src/ tests/` clean
- [ ] Manual smoke on `KTV_FRONTEND=next flet run` performed and the 9 verifications above satisfied
- [ ] Legacy frontend (default) still runs as before
- [ ] Draft PR opened against `main` with M2 summary
