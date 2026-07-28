# Milestone 3 — Search + Local Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **The main agent must verify every code change before commit.**

**Goal:** Replace the legacy SearchBar-in-dashboard (inline in `dashboard.py`) and the 5-file Local tab (`views/tabs/local/*`) with two standalone `@ft.component` screens: `SearchScreen` (debounced search over channels, reusing `ChannelGrid` and `apply_filters`) and `LocalScreen` (device video scanner with folder-expansion tiles and incremental "load more"). After this milestone the app's bottom nav shows real content on Home (M2), Search (M3), Local (M3), and Settings (placeholder — M4).

**Architecture:** SearchScreen is a lightweight wrapper: a `TextField(autofocus=True)` on top, `ChannelGrid` below. Debouncing via the `use_debounce` hook (M2). The query is a `use_state` string; `apply_filters` is reused but called with a new `"query"` key in the filter dict that does a case-insensitive substring match against channel name. LocalScreen wraps the existing `local_scanner.scan_videos()` in a `use_effect` on mount; renders a `Column` of `FolderExpansionTile` components — each tile shows a folder name, count, and on-expand renders a `ChannelGrid` filtered to that folder's videos, with incremental "load more" (append 24 items — same `PAGE_SIZE`).

**Tech Stack:** Same as M1+M2. `LocalVideo`/`VideoFolder` dataclasses from `services/local_scanner.py`. `ft.FilePicker` / `ft.StoragePaths` from `flet/controls/services/`. `use_storage` facade from M1.

**Reference:** Design spec sections C.3 (Search) and C.4 (Local). Legacy files: `dashboard.py` lines 161-175 (search), `local/views.py` (scan orchestration), `local/renderers.py` (tile rendering), `local/cards.py` (video card), `local/expansion.py` (expansion logic), `local/services.py` (FilePicker + StoragePaths wrapper).

---

## File structure

| Path | Action | Responsibility |
|---|---|---|
| `src/app_next/screens/search_screen.py` | Create | `@ft.component SearchScreen()` — debounced query + ChannelGrid |
| `src/app_next/screens/local_screen.py` | Create | `@ft.component LocalScreen()` — device scan + folder tiles |
| `src/app_next/components/video_card.py` | Create | `@ft.component VideoCard(video, on_play)` — single local-video tile |
| `src/app_next/components/folder_expansion_tile.py` | Create | `@ft.component FolderExpansionTile(folder, on_play, page_size=24)` — expandable folder with incremental load |
| `src/app_next/screens/__init__.py` | Modify | Add `SearchScreen`, `LocalScreen` exports |
| `src/app_next/components/__init__.py` | Modify | Add `VideoCard`, `FolderExpansionTile` exports |
| `src/app_next/app_shell.py` | Modify | Replace tab 1 `PlaceholderScreen("Search")` with `SearchScreen`, tab 2 with `LocalScreen` |
| `tests/app_next/test_search_screen.py` | Create | Unit tests for search + debounce integration |
| `tests/app_next/test_local_screen.py` | Create | Unit tests for scan lifecycle + folder expansion |
| `tests/app_next/test_video_card.py` | Create | VideoCard renders name + size + fires on_play |
| `tests/app_next/test_folder_expansion_tile.py` | Create | Tile shows folder name, expands on click, shows N cards per page |

**Files NOT touched:** `src/views/tabs/local/*` (legacy — deleted at M6). `src/core/*` (no changes). `src/database/*` (no changes).

---

## Task 1: `SearchScreen` component

- [ ] **Write test + implement in one step** (reuses existing code heavily)

Create `tests/app_next/test_search_screen.py`:

```python
"""Tests for SearchScreen component."""

from app_next.screens.search_screen import SearchScreen, _search_filter


def test_search_screen_marked_as_component():
    assert getattr(SearchScreen, "__is_component__", False) is True


def test_search_filter_matches_channel_name_case_insensitive():
    channels = [
        {"name": "BBC World", "url": "http://bbc"},
        {"name": "CNN International", "url": "http://cnn"},
        {"name": "Al Jazeera", "url": "http://aj"},
    ]
    result = _search_filter(channels, "bbc")
    assert [c["name"] for c in result] == ["BBC World"]


def test_search_filter_empty_query_returns_all_capped():
    channels = [{"name": f"Channel {i}", "url": f"http://x/{i}"} for i in range(100)]
    result = _search_filter(channels, "")
    assert len(result) <= 50  # MAX_SEARCH_RESULTS


def test_search_filter_no_match_returns_empty():
    channels = [{"name": "BBC", "url": "http://bbc"}]
    result = _search_filter(channels, "zzz")
    assert result == []


def test_search_filter_matches_url_as_fallback():
    channels = [{"name": "Test", "url": "http://example.com/stream"}]
    result = _search_filter(channels, "example")
    assert len(result) == 1
```

Create `src/app_next/screens/search_screen.py`:

```python
"""SearchScreen — debounced search over channels with ChannelGrid results.

Reuses apply_filters (M2) for the base filter logic and ChannelGrid (M2)
for results rendering. The only search-specific thing is the debounced
TextField and a pre-filter that matches query against channel name/URL.
"""

import flet as ft
from flet.controls.control import Control

from app_next.components.channel_grid import ChannelGrid
from app_next.components.empty_state import EmptyState
from app_next.hooks.apply_filters import apply_filters, _default_filters
from app_next.hooks.use_debounce import use_debounce
from app_next.state.app_state import AppStateCtx
from app_next.state.controller_ctx import ControllerMethodsCtx
from core.constants import LBL_SEARCH_HINT, MAX_SEARCH_RESULTS


def _search_filter(channels: list[dict], query: str) -> list[dict]:
    """Case-insensitive name/URL match, capped at MAX_SEARCH_RESULTS."""
    if not query.strip():
        return channels[:MAX_SEARCH_RESULTS]
    q = query.lower().strip()
    return [
        c
        for c in channels
        if q in c.get("name", "").lower() or q in c.get("url", "").lower()
    ][:MAX_SEARCH_RESULTS]


@ft.component
def SearchScreen() -> Control:
    state = ft.use_context(AppStateCtx)
    controller = ft.use_context(ControllerMethodsCtx)

    query, set_query = ft.use_state("")
    debounced_query = use_debounce(query, 250)

    # Re-filter on debounced query change
    visible = ft.use_memo(
        lambda: _search_filter(state.channels, debounced_query),
        [state.channels_hash, debounced_query],
    )

    favorites_set = ft.use_memo(
        lambda: (
            set(state.favorites) if isinstance(state.favorites, (list, set)) else set()
        ),
        [state.channels_hash],
    )

    def on_play(url):
        controller.play_stream(url, None)

    search_field = ft.TextField(
        value=query,
        on_change=lambda e: set_query(e.control.value),
        hint_text=LBL_SEARCH_HINT,
        autofocus=True,
        focusable=True,
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
    )

    body = (
        ChannelGrid(
            channels=visible,
            favorites_set=favorites_set,
            on_play=on_play,
            on_toggle_favorite=lambda url: _toggle_fav_simple(url, state),
            ad_service=getattr(controller, "ad_service", None),
        )
        if visible
        else EmptyState(
            title="No results",
            message="Try a different search term."
            if query.strip()
            else "Type to search channels.",
            icon=ft.Icons.SEARCH_OFF,
            action_label=None,
        )
    )

    return ft.Container(
        expand=True,
        content=ft.Column(
            controls=[
                ft.Container(
                    content=search_field,
                    padding=ft.Padding(12, 8, 12, 4),
                ),
                ft.Container(content=body, expand=True),
            ],
            spacing=0,
        ),
    )


def _toggle_fav_simple(url: str, state):
    """Fire-and-forget favorite toggle, same pattern as HomeScreen."""
    import asyncio
    from database.manager import db_manager

    async def _do():
        try:
            if url in (state.favorites or set()):
                await db_manager.remove_favorite(url)
                state.favorites.discard(url) if hasattr(
                    state.favorites, "discard"
                ) else state.favorites.remove(url)
            else:
                await db_manager.add_favorite(url)
                if isinstance(state.favorites, set):
                    state.favorites.add(url)
                elif isinstance(state.favorites, list):
                    state.favorites.append(url)
        except Exception:
            pass

    asyncio.create_task(_do())
```

**Commit:**

```bash
git add src/app_next/screens/search_screen.py tests/app_next/test_search_screen.py
git commit -m "feat(app_next.screens): SearchScreen with debounced query + ChannelGrid

Uses use_debounce (250ms) to avoid filtering on every keystroke. Case-
insensitive name/URL match, capped at MAX_SEARCH_RESULTS. Reuses M2's
ChannelGrid and the existing apply_filters architecture."
```

---

## Task 2: `VideoCard` component

- [ ] **Write test + implement**

Create `tests/app_next/test_video_card.py` and `src/app_next/components/video_card.py`. VideoCard mirrors the legacy `local/cards.py` card but with cleaner props — receives a `LocalVideo` dataclass and `on_play` callback. Shows name, file size (via `_format_size` from `local_scanner`), and a movie icon. Card is `height=140`, `border_radius=16`. Click fires `on_play(video.path)`.

Implementation details match the legacy card (verified in `local/cards.py`): `ft.Column([green dot + icon row, ft.Icon(ft.Icons.MOVIE), ft.Text(name, max_lines=2), ft.Text(formatted_size)])`.

**Commit:**

```bash
git add src/app_next/components/video_card.py tests/app_next/test_video_card.py
git commit -m "feat(app_next.components): VideoCard for local video tiles"
```

---

## Task 3: `FolderExpansionTile` component

- [ ] **Write test + implement**

Create `tests/app_next/test_folder_expansion_tile.py` and `src/app_next/components/folder_expansion_tile.py`.

FolderExpansionTile is simpler than the legacy (`local/expansion.py` + `renderers.py`). It's a `@ft.component` that:
- Receives a `VideoFolder` dataclass and `on_play` callback
- Renders a clickable header showing folder name + count
- On click, toggles expansion (local `use_state`)
- When expanded, renders a `GridView` of `VideoCard`s — first `PAGE_SIZE` (24) items, plus a "Load more" button if `len(folder.videos) > current_count`
- "Load more" increments `current_count += PAGE_SIZE`
- No show_prev/show_next swap — just incremental load

This replaces ~250 lines of legacy expansion.py + renderers.py with ~80 lines.

**Commit:**

```bash
git add src/app_next/components/folder_expansion_tile.py tests/app_next/test_folder_expansion_tile.py
git commit -m "feat(app_next.components): FolderExpansionTile incremental-load video folder"
```

---

## Task 4: `LocalScreen` component

- [ ] **Write test + implement**

Create `tests/app_next/test_local_screen.py` and `src/app_next/screens/local_screen.py`.

LocalScreen:
- On mount, runs `use_effect` → `storage = use_storage()` (loads custom paths from SharedPreferences via `ft.SharedPreferences().get("ktv_custom_video_paths")` in a fire-and-forget)
- Calls `_ensure_services(page)` (no page access — instead use `context.page` and the component's `on_mounted`)
- Triggers scan: `asyncio.to_thread(scan_videos, merge_defaults_with_custom_paths(custom_paths))` — the same merging logic as legacy `_get_scan_paths` in `local/services.py`
- State: `folders (list[VideoFolder])`, `is_scanning (bool)`, `custom_paths (list[str])`, `perm_granted (bool)` — all from `use_state`
- Renders empty state / scanning state / permission-needed state / folder list state
- Folder list is a `ListView(build_controls_on_demand=True)` of `FolderExpansionTile`
- "Add Folder" `FilledButton` at top opens FilePicker directory dialog (wiring via `context.page.run_task(_pick_dir)`)
- Refresh button re-scans

**Commit:**

```bash
git add src/app_next/screens/local_screen.py tests/app_next/test_local_screen.py
git commit -m "feat(app_next.screens): LocalScreen device scanner with incremental folder tiles"
```

---

## Task 5: Wire into AppShell + regression tests + manual smoke

Modify `src/app_next/app_shell.py` to replace tab 1 (index 1) with `SearchScreen` and tab 2 (index 2) with `LocalScreen`:

```python
if _TAB_NAMES[selected_tab] == "Home":
    body = HomeScreen(key=ft.ValueKey("home"))
elif _TAB_NAMES[selected_tab] == "Search":
    from app_next.screens.search_screen import SearchScreen

    body = SearchScreen(key=ft.ValueKey("search"))
elif _TAB_NAMES[selected_tab] == "Local":
    from app_next.screens.local_screen import LocalScreen

    body = LocalScreen(key=ft.ValueKey("local"))
else:
    body = PlaceholderScreen(
        key=ft.ValueKey(_TAB_NAMES[selected_tab]), name=_TAB_NAMES[selected_tab]
    )
```

**Full sweep:**

```bash
uv run pytest tests/app_next/ -q
uv run pytest -q  # legacy tests
uv run ruff check src/ tests/
KTV_FRONTEND=next uv run flet run src/main.py  # manual smoke
```

Manual smoke verifications:
1. Search tab opens with focus on TextField. Type "bbc" → filters results after 250ms debounce. Results appear as ChannelGrid. Clear field → full channel list returns.
2. Local tab scans device → folders appear (or "No video files found"). Tapping a folder expands it → VideoCards render. "Load more" loads next batch. "Add Folder" opens file picker.
3. Home + Settings tabs unchanged from M2 (Home) or M1 placeholder (Settings).

**Commit:**

```bash
git add src/app_next/app_shell.py
git commit -m "feat(app_next): wire SearchScreen + LocalScreen into AppShell tabs"
```