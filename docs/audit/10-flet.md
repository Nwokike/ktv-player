# 10 — flet 1.0.1 Deep Dive (installed source)

Version confirmed: `flet/version.py:19` → `flet_version = "1.0.1"`, Flutter 3.44.8.
Lazy PEP-562 exports in `flet/__init__.py` (~270 modules on first attribute access).
Companions in .venv: flet_video, flet_ads, flet_desktop, flet_cli,
flet_permission_handler, flet_platform_assets.

## Capabilities available

Component/lifecycle (`components/hooks/`): `@ft.component`, `use_state`, `use_effect`
(+ on_mounted/on_unmounted/on_updated), `use_memo`, `use_ref`, `use_callback`,
`use_context`/`create_context`/`ContextProvider`, `use_dialog` (frozen-diff portal),
`memo()`, `@ft.observable`/`Observable`. `Control.did_mount`/`will_unmount`,
`page.render(fn)`, `page.run_task(coro_fn, *args)`, `page.overlay`, `page.views`,
`page.on_app_lifecycle_state_change` (carries `e.state`, NOT `e.data`),
`page.on_keyboard_event` (single slot), `on_route_change`/`on_view_pop`/`on_close`/`on_error`.

Rendering/perf: every Control has native tooltip/badge/visible/disabled/expand/opacity/
semantics_label; LayoutControl adds animate_* (opacity/scale/rotation/offset/position),
rotate/scale/offset/flip, on_size_change, on_animation_end. ListView/GridView support
build_controls_on_demand, item_extent/first_item_prototype, cache_extent, on_scroll,
auto_scroll. Image: gapless_playback, cache_width/height, placeholder_src +
fade_in_animation, filter_quality, error_content, exclude_from_semantics.
Transitions: AnimatedSwitcher, Hero, Dismissible, Draggable/DragTarget,
InteractiveViewer, ShaderMask, Shimmer, SelectionArea, PageView, Pagelet, Screenshot,
Semantics/MergeSemantics, GestureDetector(drag_interval, hover_interval).
Full Material + Cupertino suites, Theme/ColorScheme + PageTransitionsTheme,
SearchBar/AutoComplete, SegmentedButton, ExpansionTile, ReorderableListView,
DataTable, MenuBar, NavigationDrawer/Rail, BottomSheet/BottomAppBar/Banner.

Services: Connectivity (+ get_connectivity), SharedPreferences (str|int|float|bool|
list[str] only), FilePicker, UrlLauncher (LaunchMode, WebViewConfiguration),
StoragePaths, Wakelock, HapticFeedback, Clipboard/CopyToClipboard, Share,
ScreenBrightness, Battery, sensors, ShakeDetector.

## Current usage (assessment: modern, largely correct)

83 files under src/. Heaviest usage: @ft.component + use_state (37) / use_effect (13) /
use_memo (10) / use_ref / use_context / use_dialog, @ft.observable state,
ContextProvider via page.render, Connectivity listener, FilePicker singleton,
Shimmer skeleton, GridView/ListView on-demand in folder/recent paths,
GestureDetector long-press, KeyboardListener, SegmentedButton in dialog,
SnackBar FLOATING, NavigationBar, full light/dark Theme.

## Utilization gaps (concrete, with file:line)

1. `components/focus_styles.py:52-91` — scale mutation never applies on frozen
   declarative controls; use `scale` + `animate_scale`, or delete `attach_focus_pop`.
2. `components/channel_grid.py:38-102` — manual pagination; migrate to GridView
   (like folder_expansion_tile) or add item_extent/cache_extent/on_scroll.
3. Fixed-size lists need `item_extent` + `build_controls_on_demand`:
   recently_watched.py, recently_watched_screen.py, search_screen.py,
   onboarding_screen.py, local_screen.py.
4. All logo Images need `gapless_playback=True`, `cache_width/height`,
   `exclude_from_semantics` + `semantics_label`, optional placeholder/fade.
5. Video `on_load`/`on_track_change` unwired; overlay hides on first position tick.
6. Triple-update anti-pattern (controls.py:179-192, handlers.py:26-31) — one
   owning update, not video + child + page.
7. Raw `asyncio.create_task` bypasses page task tracking (home_screen, app_shell,
   immersive_player, search_screen, add_custom_content_dialog) — use page.run_task.
8. Cards/callbacks not memoized — every liveliness tick rebuilds 24 cards.
   Wrap handlers in `use_callback`, cards in `memo`.
9. `utils/notifications.py:69-87` — SnackBar appended per notify, never removed.
   Reuse one instance or cap queue.
10. SharedPreferences/UrlLauncher constructed per call — register singletons in
    page.services like FilePicker; pass EXTERNAL_APPLICATION for store URLs.
11. Unused: HapticFeedback, Clipboard/Share, ScreenBrightness, Battery,
    SelectionArea, Dismissible, ReorderableListView, ExpansionTile, Hero.
12. `animate_*` defined in tokens/constants but never used; loading swaps are
    visible-flips — wrap in AnimatedSwitcher; add windows/macos/linux transitions.

## Pitfalls (verified)

- Frozen-control mutation silently swallowed; try/except hides it.
- `page.on_keyboard_event` single-slot — chain correctly or use KeyboardListener.
- Lifecycle event carries `e.state`, not `e.data` (main.py hidden-branch is dead).
- SnackBar overlay append without dismiss cleanup leaks.
- `Video.volume` 0-100 validated on update, not assignment.
- SharedPreferences rejects non-list[str] and some base64-prefix strings on Android.
- `FilterQuality.HIGH` blurry on Android video; LOW is safe but soft — prefer MEDIUM.
