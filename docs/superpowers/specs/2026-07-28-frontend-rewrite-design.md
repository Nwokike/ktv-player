# Frontend Rewrite — Design

- **Date**: 2026-07-28
- **Author**: Onyeka Nwokike + ZCode
- **Status**: Draft — pending implementation plan
- **Branch target**: `feat/frontend-rewrite`

## TL;DR

Full rewrite of the KTV Player frontend using Flet 0.86.3's `@ft.component` + hooks
system, mounted via `page.render(AppShell)`. The 5-tab + ExpansionTiles +
custom-pagination UI is replaced with a 4-destination bottom `NavigationBar` and
a single virtualized `GridView` with filter chips. Rolled out in parallel behind
an env toggle (`KTV_FRONTEND=next`), in six shippable milestones, then cutover.

Each section below was reviewed and approved during brainstorming.

## Brainstorming decisions (locked)

| Decision | Choice |
|---|---|
| Scope | Full frontend rewrite |
| Platforms | Android touch + Android TV / Fire Stick (D-pad). Windows desktop uses the same `NavigationBar`. |
| State model | Flet hooks (`@ft.component` + `use_state`); observable globals through context |
| Navigation | Bottom `NavigationBar`, 4 destinations: Home / Search / Local / Settings |
| Channel grid | Flat virtualized `GridView` + filter chips; no ExpansionTiles; no manual pagination |
| Ads | Kept as-is (AdService, banner + interstitial, UMP consent) |
| Deep links | Kept as-is (`ktv://play?url=…` + Open-With + fallback path) |
| Player | Kept as-is (ImmersivePlayer + flet-video engine) |
| Rollout | Parallel `src/app_next/` tree behind `KTV_FRONTEND=next`, then cutover |

## What stays / what changes

### Stays unchanged

- `src/main.py` `AppController` lifecycle, entry point, `ft.run(main, …)`, deep-link
  handling, `play_stream`, `view_pop`. **One** addition: an env-flag branch in
  `init()` to either bootstrap legacy dashboard or call `page.render(AppShell)`.
- `services/` layer — `m3u_parser`, `ChannelProvider`, `local_scanner`,
  `liveliness`, `logo_cache`, `http_client`, `liveness`.
- `database/manager.py` JSON persistence.
- `components/player/immersive_player.py` + `controls.py` + `handlers.py`.
- `services/ad_service.py` and its UMP/intersitital lifecycle.
- `core/{constants,crash_reporter,deeplink,logger_handler,logging_config,
  startup,theme,tokens,url_validator,utils}.py`.

### Replaced

- `src/views/` (15 files) — entire directory deleted at cutover.
- `src/components/ui/channel_grid.py` — replaced by `app_next/components/channel_grid.py`.
- `src/core/focus_manager.py` — replaced by `app_next/hooks/use_focus_scope.py`.
- `views/tabs/pagination.py` — deleted (no manual pagination).
- `views/dashboard_carousel.py` — replaced by `recently_watched.py`.
- `core/state.py` — augmented (one bug fix applied at Milestone 5, serving both trees).

## File map — `src/app_next/`

```
src/app_next/
├── __init__.py
├── app_shell.py                  @ft.component AppShell (page.render target)
├── routes.py                     route → screen mapping
├── state/
│   ├── __init__.py
│   ├── app_state.py              @ft.observable @dataclass AppState; AppStateCtx
│   └── controller_ctx.py         Contexts: RefreshChannelsCtx, PlayStreamCtx,
│                                 OpenLogsCtx, SetThemeModeCtx
├── screens/
│   ├── __init__.py
│   ├── onboarding_screen.py     Replaces views/onboarding.py + 2 subs
│   ├── home_screen.py           Replaces dashboard.py + channel_groups + carousel
│   ├── search_screen.py         Was inline search in dashboard
│   ├── local_screen.py          Replaces views/tabs/local/* (5 files)
│   ├── settings_screen.py       Replaces preferences_tab.py + preferences_logs.py
│   └── player_screen.py         Thin wrapper around ImmersivePlayer (pushed as View)
├── components/
│   ├── __init__.py
│   ├── channel_grid.py           Virtualized GridView
│   ├── channel_card.py           key=ft.ValueKey(url); focusable=True
│   ├── filter_bar.py             Sticky chip row
│   ├── recently_watched.py       Horizontal ListView carousel
│   ├── banner_ad_slot.py         Wraps AdService banner visibility
│   ├── country_picker.py         Dropdown/list for onboarding + settings
│   ├── loading_state.py           Shimmer / skeleton placeholder
│   ├── empty_state.py
│   ├── error_state.py
│   └── offline_flow.py
├── hooks/
│   ├── __init__.py
│   ├── use_channels.py           Loads + caches channels; maps to AppState.channels
│   ├── use_liveliness.py         Subscribes to liveliness updates
│   ├── use_storage.py            Async facade over database/manager.py
│   ├── use_theme_mode.py         Mirrors state.theme_mode → page.theme_mode + DB
│   ├── use_focus_scope.py        Replaces core/focus_manager.py — declarative
│   └── use_debounce.py           Debounce helper for search TextField
└── theme/
    ├── __init__.py
    └── component_themes.py       Extends core/theme.py with component-theme overrides
```

## Architecture

### Mount model

`AppController.init()` after-services-ready switches on `KTV_FRONTEND` env var:

- `legacy` (default during migration): existing dashboard bootstrap — no behavior
  change, in-flight `show_dialog` uncommitted work stays live.
- `next`: `page.render(AppShell)` — replaces `page.views[0].controls` and
  activates **components mode** (session-global; per-control `page.update(view)`
  still works for the classically-pushed player View — verified against
  `page.update()` source).

### State — three layers (kept; cleaned up)

#### Layer 1 — Global observable state

`src/app_next/state/app_state.py` exports a single `@ft.observable @dataclass
AppState` exposed via `create_context`. Mounted by `AppShell`.

- All list/dict fields auto-wrap as `ObservableList` / `ObservableDict`
  (verified in `flet/components/observable.py` — both `append` and reassignment
  notify subscribers).
- **The favorites field switches from `set[str]` to `list[str]`** so it's
  auto-wrapped. This **fixes the silent non-notification bug**: today
  `state.favorites.add(url)` does not fire subscribers because Python `set`
  is not wrapped, so favorite toggles only redraw because
  `_dashboard_refresh` is monkey-patched. With the new model every subscribed
  `ChannelCard` re-renders automatically when favorites change. O(1) lookup
  is preserved via a `use_memo(lambda: set(state.favorites), [state.favorites])`
  membership set passed down to cards; the storage field is a list for
  observable semantics, but in-memory lookups stay constant-time.

Fields preserved (same names): `channels`, `history`, `favorites` (now
`list[str]`), `user_country`, `has_accepted_terms`, `is_first_launch`,
`theme_mode`, `is_deep_link_launch`, `channels_hash`, `is_loading`.
DB-persistence mapping unchanged.

#### Layer 2 — Local component state

`use_state` in every interactive component (`filters`, `query`,
`selected_tab`, `selected_country`, `dialog_open`, `is_playing`, …).
Each `set_state` re-renders **only that component instance** (verified
against `Session.schedule_update` + the scheduler loop in
`__updates_scheduler`). Replaces the threaded `view_state` closure dict.

#### Layer 3 — Persistence

`database/manager.py` API unchanged (async with lock; JSON file path resolves
to mobile storage prefix automatically). Wrapped by a thin async facade in
`app_next/hooks/use_storage.py` so components call

```python
storage = use_storage()
await storage.set_user_country(cc)
```

instead of reaching into `db_manager` directly.

### Replacing `page_obj._dashboard_refresh`

Three patterns replace the monkey-patch:

1. **Observable notification** — most publishers touch observable state
   (`state.add_to_history`, `state.set_channels`); subscribers re-render
   automatically.
2. **Explicit refresh context** — `RefreshChannelsCtx = create_context(lambda: None)`;
   `AppShell` populates it with `AppController.refresh_channels`.
   Components call `use_context(RefreshChannelsCtx)()`.
3. **Cascading effects** via `use_effect` — e.g. when channels change,
   reschedule liveliness checks:

   ```python
   use_effect(
       lambda: schedule_liveliness_check(state.channels),
       [state.channels_hash],
   )
   ```

## Navigation & App Shell

`AppShell` is the top-level `@ft.component` rendered by `page.render(AppShell)`:

- **Route subscription** — `use_view_path()` reads the current URL fragment;
  `/` shows Onboarding if first launch / unaccepted terms; otherwise renders
  the four-destination scaffold.
- **Theme sync** — `ThemeCtx` mirrors `state.theme_mode` to `page.theme_mode`
  inside an `on_updated` hook.
- **AdService banner** — `BannerAdSlot` pinned above `NavigationBar` via
  `AdService` (already initialized by controller; shell feeds visibility).
- **Player** is **NOT** rendered by the shell — it's a classically-pushed
  `ft.View` via `AppController.play_stream` → `page.push_route("/play?url=…")`.
  Shell just renders the dashboard at `/dashboard`.

### NavigationBar (manual routing, verified)

```python
NavigationBar(
    destinations=[
        NavigationBarDestination(icon=ft.Icons.HOME, label="Home"),
        NavigationBarDestination(icon=ft.Icons.SEARCH, label="Search"),
        NavigationBarDestination(icon=ft.Icons.FOLDER, label="Local"),
        NavigationBarDestination(icon=ft.Icons.SETTINGS, label="Settings"),
    ],
    selected_index=selected_tab,
    on_change=lambda e: set_tab(e.control.selected_index),
)
```

`NavigationBar` has `selected_index` + `on_change` but **no built-in route
integration** (verified in `flet/controls/material/navigation_bar.py`).
Active screen is keyed by destination so switching tabs cleanly remounts
(no stale filter leakage between Categories and Local).

### D-pad / remote navigation

- Flat nav surface — only 4 destinations, all reachable on the home row.
- Semantic ordering — filter chips → grid → recently watched → destinations are
  in `Column` order so D-pad down/up walks natural reading order.
- Every interactive control sets `focusable=True` and the relevant one sets
  `autofocus=True`. Flutter's `DirectionalFocusTraversalPolicy` handles
  spatial traversal; we don't reimplement it.

## FocusManager redesign (clean, no global state)

### What Flet gives us (verified)

| Primitive | Source | Purpose |
|---|---|---|
| `Control.focusable` | `flet/controls/control.py` | Opt-in to D-pad/tab traversal |
| `Control.autofocus` | `flet/controls/control.py` | First autofocused control grabs focus on mount |
| `Control.on_focus` / `on_blur` | `flet/controls/control.py` | Per-control events |
| `KeyboardListener.on_key_event` | `flet/controls/core/keyboard_listener.py` | Back / Escape / arrow capture |

### New design — `app_next/hooks/use_focus_scope.py` (~60 lines)

```python
@ft.component
def FocusScope(child, autofocus_root=True, on_back=None):
    """KeyboardListener wrapper for TV Back/Escape; traversal is Flutter's job."""

    async def handle_key(e):
        if e.key in ("Back", "Escape") and on_back:
            await on_back(e)

    return ft.KeyboardListener(
        on_key_event=handle_key,
        content=ft.Container(autofocus=autofocus_root, content=child),
    )
```

- **No `page_obj` parameter** — `on_back` is passed in by parent screen.
- **No global counter** — `autofocus=True` on root container; component
  remount on tab switch resets focus naturally because each `ActiveScreen`
  is keyed.
- **No `_dashboard_refresh` monkey-patch** — screens receive change callbacks
  through context.
- **CLI/testable** — pure component; mount in a test Flet app with a fake
  `on_back` and trigger synthetic events without a real device.

### What gets deleted

- `src/core/focus_manager.py` (32 lines).
- `page_obj._dashboard_refresh = refresh_dashboard` assignment in `dashboard.py`.
- Every `getattr(page_obj, "_dashboard_refresh", None)` call.

## Screens

### `onboarding_screen.py` (replaces 4 files, ~150 lines)

- `use_context(AppStateCtx)` reads `is_first_launch`, `has_accepted_terms`,
  `user_country`.
- Local state: `selected_country`, `terms_accepted`, `is_loading`, `is_offline`.
- Online flow: `Column([Logo, CountryPicker, TermsCheckbox, ContinueButton])`.
- Offline flow: `OfflineFlow` component — Retry / Skip-to-offline.
- Connectivity probe runs in `use_effect` on mount (httpx head request).
- `CountryPicker` is a virtualized `ListView(build_controls_on_demand=True)`
  of `ListTile(focusable=True)`.
- Submit → `use_storage().set_user_country / accept_terms` → observable
  notification → `AppShell` re-renders → no `page.update()` needed.
- Wrapped in `FocusScope(autofocus_root=True)`.

### `home_screen.py` (replaces dashboard.py + channel_groups + carousel, ~200 lines total across 3 files)

```python
Column([
    RecentlyWatched(…),                       # hidden if history empty
    FilterBar(selected, on_change=set_filters),
    ChannelGrid(channels=visible, on_play=on_play, active_filters=filters),
])
```

- `channels, history = use_context(AppStateCtx)` from observable state.
- `filters, set_filters = use_state({"country", "category", "fav_only", "source"})`.
- `visible = use_memo(lambda: apply_filters(channels, filters), [channels, filters])`.
- `on_play(url)` → `use_context(PlayStreamCtx)` → `AppController.play_stream`
  (registered into context at shell mount, no attribute monkey-patching).

### `FilterBar` component

- `Row` of `Chip` controls, each `focusable=True`.
- Country / Category / Favorites-only / Source.
- Dropdown overlay (`MenuBar`) when tapped, populated from `classify_channel`
  outputs and `state.user_country`.
- Selecting a chip → `set_filters({...filters, "country": x})` → memo recomputes
  → grid updates.

### `ChannelGrid` component (replaces `components/ui/channel_grid.py` + `pagination.py`)

```python
GridView(
    controls=[
        ChannelCard(c, key=ft.ValueKey(c["url"]), on_play=on_play) for c in visible
    ],
    runs_count=3,  # desktop overlays wider via screen-width branch
    max_extent=160,
    child_aspect_ratio=0.75,
    cache_extent=600,
    build_controls_on_demand=True,
)
```

- **Single flat virtualized grid.** No `ExpansionTile`, no `build_page()` swap,
  no `tab_index=900` magic.
- Stable identity via `key=ft.ValueKey(channel_url)` — verified keyed
  reconciliation in `flet/controls/object_patch.py` preserves focus, scroll
  position, and animations across filter changes.
- `LoadingState` / `EmptyState` / `ErrorState` components (~40 lines each).

### `recently_watched.py`

Horizontal `ListView(horizontal=True, build_controls_on_demand=True)`. Cards
keyed by URL. Hidden when `len(history) == 0`.

### `search_screen.py` (~120 lines)

- `TextField(autofocus=True, focusable=True, on_change=on_query)`.
- `query = use_state("")`, debounced 250ms via `use_effect` + ref timer
  (`use_ref`).
- `results = use_memo(lambda: search_channels(channels, query), [channels, query])`.
- Renders the same `ChannelGrid` underneath — single source of truth for cards.
- Routed via `page.push_route("/search")` from a Search icon in shell AppBar;
  pushed view → back returns.

### `local_screen.py` (~150 lines, replaces 5 files)

- `use_channels_local()` hook wraps `local_scanner.scan_paths()` with
  `use_effect` on mount.
- State: `folders`, `is_scanning`, `permission_state`.
- `ListView` of `FolderExpansionTile` components — each expands on tap to show
  a `ChannelGrid` filtered to that folder, paginated by **incremental "Load
  more"** (append 24 items to `.controls` on tap — simpler than today's
  show_prev/show_next swap).
- Permission / scanning / empty states via shared `EmptyState` / `ErrorState`.
- `FilePicker` registered through `page.services` inside a `use_effect`
  (consistent with current uncommitted fix).

### `settings_screen.py` (~180 lines, replaces 2 files)

- M3 `SectionList` — each row a `ListTile(focusable=True)` with thumb action /
  trailing switch.
- Sections: Appearance (theme toggle), Country (re-opens picker), History
  (Clear), Custom Library (Reset), About (info), Activity Terminal (logs
  dialog).
- Theme toggle → updates `page.theme_mode` via context + DB. Uses
  `AnimatedSwitcher` (verified control) for crossfade.
- Activity Terminal: `ft.AlertDialog` containing a
  `ListView(auto_scroll=True, auto_scroll_animation=0ms,
  build_controls_on_demand=True)` fed from `AppLoggerHandler` ring buffer.
- All dialogs: `page.show_dialog(ft.AlertDialog(…))` (your migrated pattern).
- Notifications: `page.show_dialog(ft.SnackBar(…))` via a `notify(severity, msg)`
  helper shared across screens.

### `player_screen.py` (~50 lines)

- Thin wrapper around `ImmersivePlayer` — no logic change.
- Mounted as topmost `ft.View` over the shell (pushed by
  `AppController.play_stream`), not as a component in the shell tree.
- Overlay controls: existing `fv.AdaptiveVideoControls` / `MaterialVideoControls`
  — unchanged.

## Performance targets

- Home with 600+ channels in flat `GridView`: <800ms first mount.
- 60fps scroll on Fire Stick 4K.
- Re-render scope: only the dirty `Component` subtree — verified (no full-page
  re-render in components mode).
- Pre-validate at Milestone 2 by loading the real Free-TV/IPTV playlist and
  profiling.

## Rollout & cutover

### Branch strategy

- New work on long-lived feature branch `feat/frontend-rewrite` off `main`.
- New code under `src/app_next/` — does not modify old `src/views/` during
  parallel build.
- Toggle: `KTV_FRONTEND=next` (default `legacy` until Milestone 6).

### Six shippable milestones

| # | Milestone | Branch from | Lands on `main` |
|---|---|---|---|
| 1 | Scaffold `app_next/`, env toggle, shell with Onboarding + empty placeholders | `feat/frontend-rewrite` | No behavior change |
| 2 | Home + FilterBar + ChannelGrid (virtualized) | branch from #1 | Legacy unaffected |
| 3 | Search + Local screens | branch from #2 | Legacy unaffected |
| 4 | Settings + Activity Terminal dialog | branch from #3 | Legacy unaffected |
| 5 | Favorites-bug fix in `core/state.py` (general fix for both trees) | branch from #4 | Bug fix lands on legacy |
| 6 | Flip default to `KTV_FRONTEND=next`; after soak, delete legacy files | branch from #5 | Default is new UI |

Each milestone ships to `main` via PR. At cutover (M6), legacy fallback remains
for one minor release as `KTV_FRONTEND=legacy` (deprecation window).

## Risk callouts

- **`page.render` replaces `page.views[0].controls`** (verified).
  Env toggle ensures only one tree is mounted per session.
- **Components mode is session-global** (verified in
  `context.enable_components_mode`). Per-control `page.update(view)` is still
  valid for the classically-pushed player View.
- **`flet-ads` / `flet-video` stay outside the component tree** — current
  controller wiring is preserved; no hooks needed for these packages.
- **Migration gotcha**: mixing classic `page.add(…)` with `page.render(…)` on
  the same page is technically possible but counterproductive. We pick one path
  per session (env flag).

## Out of scope

- iOS / macOS / Web targets.
- Premium ad-suppression toggle.
- AdService re-architecture.
- ImmersivePlayer video engine changes.
- New build / CI jobs.

## API facts verified against installed Flet 0.86.3 source

(Via read-only exploration of
`.venv/lib/python3.13/site-packages/flet/`)

- `@ft.component` decorator wraps a function into a `Component` (subclass of
  `BaseControl`). Components can be used as children of `Container.content` or
  inside `Column.controls`. Keys work the same.
- `Page.render(component)` / `Page.render_views(component)` are sync but
  async-friendly; they replace `page.views[0].controls` / `page.views`,
  then call `context.enable_components_mode()` + session scheduler start.
- `use_state` setter is **sync**; queues deferred async update via scheduler.
  Re-render scope = **only that component instance** (verified via
  `Session.schedule_update` + `Component._schedule_update`).
- `@ft.observable` works on `@dataclass` classes. `ObservableList` auto-wraps
  list/dict fields; `append`, `__setitem__`, and reassignment all notify.
- `GridView` / `ListView` have **no `item_builder` callback**; you populate
  `.controls = [...]` and rely on `build_controls_on_demand=True` (Flutter's
  lazy mounting of off-screen items via SliverList/SliverGrid).
- Async event handlers are supported (verified in `base_control._trigger_event`
  — branches on `iscoroutinefunction`).
- Keys: `key=ft.ValueKey("id")` on any control; reconciliation uses keys for
  React-style identity matching.
- `NavigationBar` — manual (`selected_index` + `on_change`); no built-in route
  integration.
- `page.update(*controls)` patches the whole page when called with no args,
  specific controls when given args. `page.schedule_update()` is a deferred
  batched update (used internally by hooks).
- `Container(content=MyComp())` works — `Component` is a `BaseControl`.
- Per-control delta between `Column` (eagerly builds all children) and `ListView`
  / `GridView` (lazy mount via `build_controls_on_demand`).
- `ScrollableControl.auto_scroll` + `auto_scroll_animation` for the Activity
  Terminal log viewer.
