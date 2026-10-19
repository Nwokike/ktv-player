# v2.2.0 to v2.3.0 Change Ledger (Investigation)

**Baseline:** `v2.2.0` = `42192d4` (20 Nov release, build 20)
**Head:** `0224540` (build 21)
**Range:** 43 commits, 138 files changed, **+7210 / -2607** in `src/`, 68 source files touched
**Verdict:** 2.3.0 is **not shippable**. This document logs every change so each one can be re-planned against 2.2.0 deliberately instead of by accident.

**Method.** Three independent read-only agents, one per area, each diffing `v2.2.0..HEAD` and reading both sides of every file in their scope. Every entry below cites `file:line`. Nothing here is inferred from commit messages alone; where a change was made and then undone, the net effect on HEAD is stated.

**How to read the status column.**

| Status | Meaning |
|---|---|
| **WORKS** | An automated test pins the behaviour, and the behaviour is what was intended. |
| **UNVERIFIED** | The code is correct as far as reading goes, but nothing has exercised it on a real phone or TV. |
| **BREAKS** | It changes behaviour in a way the user is likely to feel, or it broke something already. |
| **REVERTED** | It was changed and then undone. Net zero on HEAD unless stated otherwise. |
| **DEAD** | It is in the tree but nothing calls it. |

**The single most important caveat:** a large share of what is marked WORKS is "works per an automated test", not "works on a device". The notification stack, the Android delete consent flow, MediaStore discovery, PiP and TV detection have **no** device-verification record anywhere in this repo.

**What was checked a second time.** The highest-risk claims were re-verified by hand against the source, not taken on the agent's word:

| Claim | Verification |
|---|---|
| The HLS proxy enforces TLS for every host | **Confirmed.** `src/main.py:134` is `HLSProxy()` with no arguments; `hls_proxy.py:137` defaults `insecure_hosts` to an empty set; `verify=False` is mounted only per listed host at `hls_proxy.py:151-156`. No host is listed anywhere. |
| The checkout watcher aborts on 402/403 | **Confirmed.** `kiri_license.py:45` `WATCHER_ABORT_CODES = frozenset({402, 403})`; the abort is at `premium_service.py:277`. |
| The `file://C|` pipe form is fixed but untested | **Confirmed.** The normalisation is at `url_validator.py:61`. `grep -rn "C|" tests/` returns nothing. |
| The log level default dropped to INFO | **Confirmed.** `logging_config.py:25` is `def setup_logging(level: int = logging.INFO, ...)`. |
| The Premium UI fix is `page.premium` on the page | **Confirmed.** `src/main.py:181` is `self.page.premium = self.premium`. |
| Mid-grid banner ads were removed | **Confirmed.** v2.2.0 imported `AD_ROW_INTERVAL` and called `ad_service.get_standard_banner_ad()` between chunks; HEAD has no `AD_ROW_INTERVAL` import and a single memoised `build_banner_ad(page)`. |
| The nav bar might show during onboarding | **CORRECTED. This was a false positive.** The agent reasoned from the missing `_should_show_onboarding` branch in the effect. But `_ShellNavigationBar` is only mounted inside the dashboard `else` branch (`app_shell.py:225-233`), and onboarding takes the `if` branch at `app_shell.py:186`, so the bar is never installed during onboarding. The net behaviour matches 2.2.0. |

---

## Part 0: The shape of the release

### 0.1 Timeline

```
66c337a  Publish version.json: 2.2.0 update feed
937c211  2.3.0: eight-phase hardening pass, verified by release-audit swarm   <- the big one
934f27f  fix: four 2.3.0 regressions found by user testing
5ae8072  fix: three more 2.3.0 defects found by the second audit wave
0004308  fix: white player with audio - restore the expanding FocusScope wrapper
87aab63  fix: a failed live stream could not be closed - Back was a no-op
3435e76  ci: restore pre-release publishing so a tagged build is never Latest
7d4c658  fix: four release-audit findings, each verified before fixing
4d26fb7  fix: the three regressions you found by opening the app, plus the Video-widget revert
2bee4e1  fix: restore the premium wiring that 2.3.0 dropped       <- THE RESET back to the 2.2.0 base
ed47a1c  fix: re-apply the two player fixes onto the 2.2.0 base
fb625bb  revert: Home screen scroll/focus - remove the AnimatedSwitcher from the grid
bc163e0  fix: a dead custom playlist no longer poisons every boot
943f671  feat: system notifications for screenshot, favourite and channel recovery
4567d88  fix: commit the notify_service module the notifications commit imported
4eb164e  Stop the checkout watcher from burning the Worker's KV write budget
8d81f08  revert: remove the playlist-failure cooldown it introduced
07af069  ci: patch the Android project for notifications (both APK and AAB)
6717a9d  feat: notifications for payment landing and a licence being revoked
74d23fb  feat: notify when a new version is available
5640808  feat: notify when a device scan finds new videos
3761998  feat: notify when a background channel refresh changes the list
522de77  fix: defects the verification agents found in the notification work
22ceed6  style: satisfy C408 on CI's ruff (dict() to literal)
385abd8  one self-adapting SVG for the README (drop icon_white.svg/png)
0224540  assets: restore the original icon_white.svg
```

### 0.2 The two structural problems, stated plainly

**Problem 1: one enormous commit did almost everything.** `937c211` ("eight-phase hardening pass") changed the player, the cards, the grid, the shell, the dialogs, the theme, the database and the network stack in a single commit. Every regression the user then reported traces back to it, and because it was one commit, every fix had to be a separate corrective commit on top of it. That is the opposite of how a release should be shaped.

**Problem 2: the reset at `2bee4e1` silently re-broke things.** The commit reset six files to the v2.2.0 base to restore licensing. That reset also wiped the close-path fix and the startup-reconnect gate that had already landed. `ed47a1c` then re-applied exactly two fixes. The licensing restore was correct; the collateral damage was not noticed at the time and was only found by the user.

**Problem 3 (found by the agents): a fix deleted its own tests.** `fb625bb` reverted the Home-screen `AnimatedSwitcher` and, in the same commit, deleted 847 lines of tests across ten files. The commit message mentions only the grid. Most of that test content was re-added later, but three behaviours are now correct on HEAD with **no automated pin at all**:

- the Home grid must be a plain expanding scrolling `Column` (no `AnimatedSwitcher`, no per-page `key`)
- the Quality and Audio chips must stay invisible until the probe finds real options
- the `file://C|/Windows/...` pipe-separator bypass must be rejected

### 0.3 A release-blocking process finding

The notification commit `943f671` imported `services.notify_service` but **did not commit the module**. The app would have raised `ImportError` on every boot. Local tests passed because the file existed on disk. Only CI caught it, 43 minutes later, in `4567d88`.

The lesson is direct: **"803 tests pass" was never evidence that the app boots.** On this codebase, a green suite and a bootable app are different claims. Any re-plan needs a boot smoke check that imports `src.main` in a fresh interpreter, not a unit test.

---

## Part 1: The player, the shell and the components

### 1.1 The four reported symptoms, traced to their exact commits

| Symptom | Root cause | Introduced by | Fixed by | Net on HEAD |
|---|---|---|---|---|
| White video surface, audio plays | The expanding `Container` wrapper around `KeyboardListener` was removed. `ft.KeyboardListener` extends `Control`, not `LayoutControl`, so `expand=True` on it is accepted and ignored. The `Stack` underneath got no bounds, so mpv decoded into a texture with no area. | `937c211` | `0004308` | Wrapper present at `src/hooks/use_focus_scope.py:65-72`. **WORKS** (tested), not re-confirmed on device. |
| Player could not be closed | `handle_close()` was called before `on_close()`. `handle_close` latches `_is_closing`; the outer `_close_player()` then sees "close already in flight", bails, and the view never pops. | `937c211` | `87aab63`, wiped by `2bee4e1`, re-applied by `ed47a1c` | `_on_back` calls `self.on_close()` only (`immersive_player.py:1248-1262`); `main.py:780-790` likewise. **WORKS** (tested). |
| "Reconnecting" flash before every channel plays | `flet_video` fires `complete` as soon as a playlist is attached, before mpv decodes anything. Treating that as end-of-stream reset the playlist under the in-flight `play()`. | `937c211` | `4d26fb7`, wiped by `2bee4e1`, re-applied by `ed47a1c` | `_playback_started` gate at `immersive_player.py:243, 716, 727, 1202-1212`. **WORKS** (tested). |
| Home would not scroll, D-pad could not page | The grid was wrapped in `ft.AnimatedSwitcher` with a per-page `key`. The switcher carries a single `content` and no `expand`, so it sized to its child; the inner `Column` with `scroll=AUTO` lost its bounded height; the per-page `key` swapped the whole subtree on every page turn. | `937c211` | `fb625bb` | Plain `ft.Column(controls=sections, expand=True, scroll=ft.ScrollMode.AUTO)` at `channel_grid.py:199-210`. **REVERTED to v2.2.0 shape. No test pins it.** |
| Quality/Audio chips showed on channels with no options | `_make_option_chip` rendered `content=row` with a default label immediately, instead of leaving the chip zero-size until the probe found real variants. | `937c211` | `4d26fb7`, then `2bee4e1` | Chip code is byte-identical to v2.2.0 (`controls.py:120-128, 149-157`). **REVERTED. The two tests that pinned it were deleted. No test pins it.** |

The deeper lesson, and the reason the user was right to be angry: **the first audit wave reported "no blockers" from code reading alone.** Position, duration and load events prove decoding. They do not prove rendering. The white player produced a perfectly healthy stream and a perfectly broken picture. Only diffing the serialized control tree, or looking at the screen, caught it.

### 1.2 Player core

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| P1 | `complete` is ignored until real playback has started (`_playback_started` flag) | flet_video signals `complete` on playlist attach | no "Reconnecting stream (1/5)" flash before picture | **WORKS** | `test_player_handlers.py::test_complete_before_playback_is_ignored`, `::test_positive_position_tick_opens_the_completion_path`, `::test_zero_tick_does_not_open_the_completion_path` |
| P2 | Back/Escape routes only through `on_close()` | `handle_close` latched `_is_closing` and deadlocked the pop | Back always leaves the player | **WORKS** | `test_release_2_3_0_regressions.py::test_back_paths_never_call_handle_close_first` |
| P3 | Tap-to-close calls `on_close()` and resolves the page at tap time | same deadlock; the old code captured `self.page` at bind time | tapping the error overlay closes the player | **WORKS** | same test, tap branch |
| P4 | `_keep()` keeps strong references to fire-and-forget tasks | asyncio holds only weak refs to tasks | PiP and position checkpointing are no longer silently dropped | **UNVERIFIED** | none |
| P5 | `_await_result()` helper wraps a coroutine for `page.run_task` | `run_task` takes a function, not a coroutine | none directly | **WORKS** | `test_release_audit_fixes.py::test_immersive_player_await_helper_for_run_task` |
| P6 | Nine `try/except: pass` converted to `contextlib.suppress` | ruff SIM105 | none | **WORKS** | n/a |
| P7 | Screenshot posts a system notification | the native fullscreen route draws no Flet tree, so the in-app toast is invisible there | an Android notification confirms the screenshot | **UNVERIFIED** | not at this call site |
| P8 | Favourite toggle posts a system notification | same reason; the star's green colour is not visible in native fullscreen | an extra notification on every favourite toggle, including removal | **UNVERIFIED** | `test_notifications.py::test_feedback_posts_on_the_silent_channel` |
| P9 | `_on_complete` takes an optional event | testability | none | **WORKS** | `test_player_handlers.py::test_complete_before_playback_is_ignored` |
| P10 | `Video` widget constructor values: `filter_quality` MEDIUM to LOW, `pause/resume_upon_entering_background_mode` False to True, `title` becomes the stream title | 2.3.0 tuning | none | **REVERTED** to v2.2.0 values at `immersive_player.py:338-340, 377`. **Pinned.** | `test_deep_link_pip_fixes.py::test_video_defaults_match_the_22_baseline`, `::test_video_title_is_the_stream_title` |
| P11 | `handlers.py` fit-change update wrapped in `contextlib.suppress` | style | none | **WORKS** | n/a |

### 1.3 Focus, keyboard and card styling

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| F1 | The expanding `Container` wrapper around the `KeyboardListener` is restored | `KeyboardListener` is not a `LayoutControl`; without the wrapper the player `Stack` has no bounds | video renders instead of a white rectangle | **WORKS** | `test_focus_scope.py::test_focus_scope_expands_its_wrapper_container`, `::test_keyboard_listener_is_not_a_layout_control` |
| F2 | `FocusScope` renamed to `focus_scope`, `FocusScope` kept as an alias | PEP8; the old name was misleading (it is a back-key interceptor, not a focus trap) | none | **WORKS** | n/a |
| F3 | `autofocus=True` on the `KeyboardListener` | an unfocused overlay swallowed the first Back press | the first Back press reliably closes the player | **UNVERIFIED** | none |
| F4 | `"Go Back"` removed from `_BACK_KEYS` | it is not a real `KeyboardEvent.key` value | a device emitting `Go Back` is no longer caught by the scope (platform Back still works) | **UNVERIFIED** | `test_focus_scope.py::test_back_keys_verified_set` |
| F5 | Re-entrancy guard and exception logging in the scope's key handler | a second Back during an await could start two close sequences | double Back cannot start two closes; a failing close is logged | **WORKS** | `test_focus_scope.py::test_on_back_exception_does_not_propagate`, `::test_on_back_fires_for_back_key/escape/browser_back`, `::test_on_back_does_not_fire_for_arrow_keys` |
| F6 | `focus_styles.py` rewritten: `attach_focus_pop` deleted, `card_button_style` reworked with PRESSED and DISABLED states, `overlay_alpha` and `radius` validated | the FOCUSED border/overlay is the only focus cue that survives Flet's frozen-component rule | pressed cards get a visible pressed state; no scale pop on focus | **WORKS** | `test_focus_pop.py::test_focus_styles_exposes_only_the_button_style`, `::test_focused_state_is_the_cue`; `test_focus_cards.py::test_channel_card_has_style_preserving_corners_and_padding` |
| F7 | `ChannelCard` and `VideoCard` no longer write `control.scale` on focus/blur | the card is the body of an `@ft.component` and is frozen after render, so every focus event raised `Frozen controls cannot be updated` | no focus-time error spam | **WORKS** | `test_focus_pop.py::test_card_carries_no_scale_mutation_handlers`, `::test_no_source_file_writes_scale_on_focus`; `test_release_2_3_0_regressions.py::test_cards_carry_no_focus_scale_mutation` |
| F8 | `src/hooks/use_autofocus.py` deleted; screens use the native `autofocus=` prop | the imperative `await control.focus()` workaround could fire on a frozen control | onboarding checkbox, Home add button, Local scan button, header search field take focus on mount. The Settings switch deliberately does not. | **WORKS** | `test_autofocus_landing.py` (8 tests) |
| F9 | `use_keyboard_shortcuts`: Cmd+K / Cmd+R now fire | macOS has no Ctrl | Ctrl+K and Ctrl+R work on Mac | **UNVERIFIED** | `test_keyboard_shortcuts.py::test_cmd_k_fires_search_on_macos` |
| F10 | `use_keyboard_shortcuts`: Alt+Escape no longer pops the player | an Alt-modified key is a different chord | Alt+Esc no longer closes the player | **UNVERIFIED** | `test_keyboard_shortcuts.py::test_alt_escape_does_not_pop` |
| F11 | `use_keyboard_shortcuts`: identity-guarded cleanup | unmounting must not clobber a newer handler | prevents handler nesting across remounts | **WORKS** | `test_keyboard_shortcuts.py::test_cleanup_keeps_newer_handler`, `::test_cleanup_on_remount_prevents_handler_nesting` |
| F12 | `use_keyboard_shortcuts`: `None` key handled, exception narrowed to `RuntimeError` | `e.key` can be `None`; `context.page` raises `RuntimeError` | a keystroke with no key no longer crashes the handler | **UNVERIFIED** | `test_keyboard_shortcuts.py::test_none_key_does_not_crash` |

### 1.4 Home screen, grid and cards

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| G1 | `AnimatedSwitcher` + per-page `key` wrapper on the grid | 2.3.0 wanted a cross-fade | **broke Home scrolling and D-pad paging** | **REVERTED**, unpinned | **none** |
| G2 | Mid-grid interleaved banner ads removed; a single memoised bottom banner remains | a per-render `build_banner_ad(page)` re-created a native ad view on every liveliness tick | the Home grid no longer shows a banner between every N channels. **Revenue-visible, and likely an unintended casualty of the rework.** | **UNVERIFIED** | none |
| G3 | Page clamping moved out of render into an effect | setting state during render is illegal in Flet | narrowing a filter now lands on the last page instead of an empty grid | **UNVERIFIED** | none |
| G4 | Liveliness and logo seeding keyed on content identity (`tuple` of URLs) not list length | a filter swap with the same count must still re-seed | dots and logos populate after a filter change even at constant count | **UNVERIFIED** | none |
| G5 | Prev/Next pagination became real `ft.OutlinedButton`s | `ft.Container(on_click=...)` was invisible to the D-pad and still fired when "disabled" | the D-pad can reach Previous/Next; a disabled button does nothing | **UNVERIFIED** | none |
| G6 | `LivelinessChannelCard`, a per-card subscription component | the page-level subscription rebuilt all 24 cards per tick | only the changed dot repaints | **WORKS** | `test_per_card_liveliness.py` (5 tests) |
| G7 | `ChannelCard` logo gained `placeholder_src="/icon.png"` | avoid a blank white box while a remote logo loads | placeholder instead of an empty box | **UNVERIFIED** | none |
| G8 | Grid cards get `key=url` | stable identity across rebuilds | less flicker on a list change | **UNVERIFIED** | none |
| G9 | Screen-level liveliness subscription removed from `home_screen.py` | per-card ownership | scrolling stays smooth while dots fill in | **WORKS** | `test_per_card_liveliness.py` |
| G10 | Filter updates use a functional state update | the render closure could be stale | a pill change is never lost | **UNVERIFIED** | none |
| G11 | Dead Home search state removed (`search_input`, `debounced_search`, `_commit_search`) | it was write-only; the Header opens the Search screen | none | **UNVERIFIED** | none |
| G12 | Play double-tap guard (`_play_in_flight` ref) | rapid taps stacked two `play_stream` races | double-tapping a channel opens one player | **UNVERIFIED** | none |
| G13 | Foreground-refresh marker set on the Home refresh button | the toast is the confirmation, so no notification as well | one toast, not a toast plus a shade entry | **WORKS** | `test_notifications.py::test_foreground_refresh_is_exempt` |
| G14 | Recently-Watched view: duplicate-route guard, `AppBar`, explicit back | stacking duplicates grew the back stack without bound | opening it twice no longer grows the stack; it gains a title bar | **WORKS** | `test_back_stack.py::TestViewPopOverlay::test_view_pop_closes_history_overlay` |
| G15 | Banner ad memoised in `home_screen.py` | the old per-render build re-created a native ad view on every 500ms tick | no repeated ad-view churn | **UNVERIFIED** | none |
| G16 | Filter-reset notice is re-armed after a genuine reset | 2.2.0 only ever notified once | a second genuine reset later in the session notifies again | **UNVERIFIED** | none |
| G17 | Auto-load scheduled on the page loop | unmount during flight set state on a dead component | no crash if Home unmounts mid-load | **UNVERIFIED** | none |

### 1.5 Local video cards, folder tile, recently watched

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| V1 | `VideoCard`'s Options button moved out of the play button into a `Stack` sibling | nesting relied on gesture arbitration with no `stopPropagation`; on some targets tapping Options also started playback | Options no longer starts playback; one focus stop per card | **UNVERIFIED** | `test_focus_cards.py` (structure only, not the gesture) |
| V2 | `VideoCard`'s preview is always an `ft.Image` with a placeholder | the prewarm mutates `video.thumbnail` post-build, and an Icon-vs-Image branch at build time can never upgrade | the thumbnail appears in place after prewarm | **UNVERIFIED** | `test_video_thumbnails.py` |
| V3 | `VideoCard` shows a duration badge | informational | local tiles show the runtime | **UNVERIFIED** | none |
| V4 | `FolderExpansionTile`: `GridView` replaced by a wrapping `ft.Row(wrap=True)` | a scrollable `GridView` with `expand=True` inside an unbounded `Column` is a layout hazard | expanding a folder no longer fights the outer list's scroll | **UNVERIFIED** | `test_release_audit_fixes.py::test_folder_tile_uses_wrapping_row` (shape only) |
| V5 | `FolderExpansionTile` uses functional state updaters | rapid double-taps read a stale closure | double-tapping the header no longer loses a toggle | **UNVERIFIED** | none |
| V6 | `FolderExpansionTile` shows `total` and an "Empty folder" state | the count now comes from the loaded list | empty folders say so | **UNVERIFIED** | none |
| V7 | `RecentlyWatched` uses the shared `utils.history.resolve_entry` | de-duplication; both views previously got it wrong the same way | entries with no URL are dropped instead of rendering broken | **UNVERIFIED** | `test_recently_watched.py`, `test_focus_cards.py` |
| V8 | `RecentlyWatched` logo gained `placeholder_src="/icon.png"` | avoid a blank box | no blank box while loading | **UNVERIFIED** | none |

### 1.6 Filter bar and header

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| FB1 | The country menu's first entry changed from "Cancel" (which reset to the user's *default country*) to "All Countries" (which resets to `all`) | the old behaviour made the country pill look selected almost always | the pill is unhighlighted until a country is chosen, and "All Countries" means all countries. **Changes what a user sees when they dismiss the country menu.** | **UNVERIFIED** | none |
| FB2 | "Cancel" relabelled "All Categories" and "All" | clarity | labels only | **UNVERIFIED** | none |
| FB3 | `PopupMenuItem`s carry `checked=` | clarity | the open menu shows a check on the active filter | **UNVERIFIED** | none |
| FB4 | Filter lists sorted case-insensitively | determinism | menu ordering changed | **UNVERIFIED** | none |
| FB5 | The Fav pill rebuilt with the shared `_pill()` helper | it had drifted from the other pills | the Fav pill matches the others | **UNVERIFIED** | none |
| FB6 | Filter pill vertical padding increased (12 to 16) | a ~48px touch target | **the pills are visibly taller on Home** | **UNVERIFIED** | none |
| FB7 | Filter pills gained tooltips | discoverability | hover text only | **UNVERIFIED** | none |
| FB8 | `on_add_content` is arity-tolerant | popup-menu clicks pass an event, direct callers do not | the "+" always opens the dialog | **UNVERIFIED** | `test_release_2_3_0_regressions.py::test_filter_bar_plus_is_text_not_icon` |
| FB9 | The filter bar's "+" is a plain text "+" pill, not an icon | the Header already owns the add icon | one plus icon, one text plus, as in 2.2.0 | **WORKS** | same test |
| H1 | `Header` keeps a local theme-darkness mirror so the sun/moon icon flips in the same frame | `toggle_theme()` calls `page.update()` but does not re-run the Header component | the icon changes immediately instead of lagging | **WORKS** | `test_release_2_3_0_regressions.py::test_theme_toggle_sets_local_state` |
| H2 | The version chip is driven by lifted props | "the chip reads props, not the observable" | the chip repaints reliably | **UNVERIFIED** | `test_header.py::test_version_chip_reactive_props` and 2 more |
| H3 | The version chip no longer reads "Update: Update Available!" | a persisted flag with a missing payload produced doubled text | the chip reads correctly | **WORKS** | `test_release_2_3_0_regressions.py::test_version_chip_label_missing_is_not_doubled` |
| H4 | Header callbacks are arity-tolerant | Flet dispatches both arities | header actions fire either way. **An async callback would still silently drop its coroutine.** | **UNVERIFIED** | none |
| H5 | The Header brand mark is no longer tinted, and the action cluster scrolls rather than overflowing | the SVG is blue line-art; `SRC_IN` tinting flattened it to a silhouette | **the header logo now renders in its real blue** | **UNVERIFIED** | none |
| H6 | The Header resolves the page and theme safely off-session | `getattr` cannot catch a raised exception | prevents a crash outside a session | **WORKS** | `test_header.py` |

### 1.7 Version dialog

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| VD1 | The dialog is a tracked singleton | a second open stacked duplicates | opening it twice no longer stacks | **UNVERIFIED** | none |
| VD2 | The Check button morphs the dialog in place instead of close-check-reopen | the old sequence left a silent window where a failure looked like nothing happened | a spinner shows in place; a failure restores the dialog and toasts | **UNVERIFIED** | none |
| VD3 | Download buttons use `ft.OpenUrl` actions instead of pop-then-launch | in-gesture, never popup-blocked | the release page opens in a browser tab | **UNVERIFIED** | none |
| VD4 | Link launches are scheme-checked (`http`, `https`, `mailto`, `market`) | a malformed link in the changelog | "could not open link" rather than a generic network error | **UNVERIFIED** | none |
| VD5 | Mandatory updates re-show when dismissed | a mandatory update cannot be dismissed past | the dialog reappears | **UNVERIFIED** | none |
| VD6 | `_info_dict` normalises `UpdateInfo` or dict at the dialog boundary | the storage layer holds a typed object | none directly | **UNVERIFIED** | none |
| VD7 | The dialog body width is responsive | 2.2.0 hard-coded 360 | the changelog body shrinks on a narrow phone | **UNVERIFIED** | none |
| VD8 | "Android TV is GitHub APK only" | documentation | **no Android TV behaviour changed. This is a docstring only, do not mistake it for a shipped feature.** | **REVERTED-equivalent** | none |

### 1.8 Add-custom-content dialog

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| AC1 | The playlist is fetched **before** it is saved | saving first said "Playlist added!" for a URL that 404s, and the dead row sat in storage being refetched every boot | a bad URL produces an error, not a false success, and no dead row is written | **WORKS** | `test_add_custom_content_dialog.py`, `test_iptv_service.py` |
| AC2 | URL validation parses instead of prefix-matching | prefix matching accepts `https://` with no host | "not-a-url" is rejected with a clear message | **UNVERIFIED** | none |
| AC3 | Errors are shown inline on the URL field | 2.2.0 showed only a generic toast | the user is told exactly why the add was rejected | **UNVERIFIED** | `test_release_audit_fixes.py::test_add_content_dialog_uses_error_not_error_text` |
| AC4 | A double-submit guard (`in_flight` ref) | the `is_adding` state is stale between click and rebuild | double-tapping Add cannot add twice | **UNVERIFIED** | none |
| AC5 | The cooldown is surfaced to the user | 2.2.0 silently disabled the Add button | the user learns why Add is disabled | **UNVERIFIED** | none |
| AC6 | The playlist name is derived from the URL basename | 2.2.0 hard-coded "Playlist" | the entry is named "sports" instead of "Playlist" | **UNVERIFIED** | none |
| AC7 | The modal-stack push is a ref with an unmount cleanup | state lags; an unmount left a phantom entry | the back stack no longer accumulates phantom "add_content" entries | **UNVERIFIED** | `test_back_stack.py` |
| AC8 | `on_added` is awaited instead of fire-and-forget | surface failures | the grid refresh after adding is guaranteed to complete | **UNVERIFIED** | none |
| AC9 | The URL field gained `autofocus=True` and `max_length=2048`; the SegmentedButton gained `allow_empty_selection=False` | polish | the field is focused on open; the type selector cannot be empty | **UNVERIFIED** | none |
| AC10 | `_reset` no longer clears the cooldown timestamp | clearing would disable the double-submit guard | the cooldown actually applies | **UNVERIFIED** | none |

### 1.9 App shell and `main.py`

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| S1 | `AppShell` mutates the controller instance instead of replacing it with `dataclasses.replace` | the 2.3.0 rework produced a *copy*, so the controller read its own defaults and Back on a non-Home tab exited the app | Back on Local/Settings returns Home | **WORKS** | `test_release_audit_fixes.py::test_shell_mutates_controller_instance`, `test_back_stack.py::test_handle_back_on_secondary_tab_returns_home` |
| S2 | The navigation bar is owned by an `_ShellNavigationBar` component mounted inside the tree, instead of a `use_effect` in `AppShell` that located the view and assigned `navigation_bar` | `page.render()` takes controls, not a View, so the bar cannot be returned as part of the tree itself | the bar appears and disappears with the shell, and is cleared on unmount. **The 2.2.0 effect had an explicit `_should_show_onboarding(state)` branch that cleared the bar during onboarding. That branch is gone from the effect, but the net behaviour is unchanged: `_ShellNavigationBar` is only mounted inside the dashboard `else` branch (`app_shell.py:225-233`), and during onboarding `screen` is `OnboardingScreen` (`app_shell.py:186-191`), so the bar is never installed at all. Verified by reading both versions, not inferred.** | **WORKS** | `test_release_audit_fixes.py::test_dashboard_view_skips_blank_and_play` |
| S3 | `_dashboard_view` skips `/blank` and `/play` | the `/blank` underlay sits at index 0 | the bar attaches to the right view | **UNVERIFIED** | same test |
| S4 | `_on_tab_change` range-guards the index | an out-of-range index raised `IndexError` | ignored instead of crashing | **UNVERIFIED** | none |
| S5 | Search-screen play goes through `page.run_task` and passes the title | 2.2.0 used a bare task and dropped the title | a channel opened from Search carries its title | **UNVERIFIED** | none |
| S6 | `toggle_favorite` argument order corrected | 2.2.0 called `toggle_favorite(state, url)` but the function takes `(url, state)` | **toggling a favourite from Search actually works. This was broken in 2.2.0.** | **UNVERIFIED** | none |
| S7 | `ControllerMethods` defaults made variadic with real names | the default path must never `TypeError` | none | **WORKS** | `test_release_audit_fixes.py::test_noop_update_check_accepts_keyword` |
| M1 | `_play_lock` is built in `__init__`, not lazily | two entrants could each build their own | a rapid double-tap opens the player once | **UNVERIFIED** | `test_deep_link_pip_fixes.py::test_duplicate_play_suppressed_while_play_in_flight` |
| M2 | The HLS proxy socket bind is deferred past the first frame | awaiting it held the first frame hostage on slow binds | faster boot. **Trade-off: the first seconds may use direct stream URLs if the proxy is not yet bound.** | **UNVERIFIED** | none |
| M3 | `db_manager.init_db()` moved after service construction, still pre-render | it is one local read every load depends on | none expected | **UNVERIFIED** | none |
| M4 | Favourites are loaded sorted | determinism | a stable alphabetical favourites order | **UNVERIFIED** | none |
| M5 | The lifecycle checkpoint save keys on `e.state`, not `e.data` | flet 1.0.1 carries `e.state`; there is no `e.data`. 2.2.0's own comment said "matches nothing on flet 1.0.1" | **minimising the app while a video plays now actually saves the resume position.** It never did in 2.2.0. | **WORKS** | `test_deep_link_pip_fixes.py::TestLifecycleStateDispatch`, `::test_hide_state_saves_not_data` |
| M6 | Global errors are suppressed only when they look player-related | 2.2.0 suppressed everything while any `/play` view existed | network errors during playback now show a toast instead of being swallowed. **More error toasts than before.** | **UNVERIFIED** | none |
| M7 | `_close_already_saved` is a single shared close guard | so the four guard sites cannot drift | none | **WORKS** | `test_deep_link_pip_fixes.py::test_view_pop_skips_when_close_already_saved` |
| M8 | A single-view player exits the app instead of stranding the user | a cold "Open With" launch leaves one `/play` view with nothing beneath it | closing such a player exits the app | **UNVERIFIED** | `test_release_2_3_0_regressions.py::test_single_view_player_close_exits_not_strands` |
| M9 | The `/blank` underlay is pushed by both deep-link branches | the fallback branch omitted it, stranding single-view stacks with no position save | a browser deep link behaves like a `ktv://` deep link | **UNVERIFIED** | `test_deep_link_pip_fixes.py::test_fallback_appends_blank_underlay` |
| M10 | `_b64url_param` normalises the deep-link query parameter | a raw percent-decoded URL failed base64 validation and the user landed on a black view with no error | a browser link to a video actually plays | **UNVERIFIED** | `test_release_2_3_0_regressions.py::test_b64url_param_encodes_raw_and_is_idempotent` |
| M11 | The `/?url=` fallback forwards `headers` and `referer` | dropping them made referer-locked streams unplayable from a browser link | referer-protected streams play from a browser link | **UNVERIFIED** | `test_release_2_3_0_regressions.py::test_fallback_forwards_headers` |
| M12 | `merge_cdn_headers` merges per key instead of replace-or-nothing | the old version dropped every caller header whenever an override matched | custom headers survive | **UNVERIFIED** | `test_back_stack.py::test_cdn_headers_merge_per_key` |
| M13 | `push_modal` ignores a duplicate push; `close_modal`/`pop_modal` are no-ops on an empty stack | 2.2.0's `pop_modal` raised `ValueError` on a missing name | no crash when a modal is closed twice | **WORKS** | `test_back_stack.py` (4 tests) |
| M14 | The notification service is constructed and wired at boot | the feature | **a runtime permission prompt appears on first use on Android 13+** | **UNVERIFIED** | `test_notifications.py` |
| M15 | A notification tap runs the deep-link path; an http(s) payload opens the browser | `parse_deep_link` gates to the `ktv://` scheme only | tapping "new version available" opens the release page | **UNVERIFIED** | `test_notifications.py::test_update_payload_is_the_release_url` |
| M16 | A new release posts a system notification once per version | a non-mandatory update was invisible unless the user opened Settings | one notification per new version | **UNVERIFIED** | `test_notifications.py::test_update_announces_once_per_version` and 2 more |
| M17 | `premium.shutdown()` is called without `await` | 2.2.0's `PremiumService` exposes only a sync `shutdown()`; awaiting raised `TypeError` which a `suppress` swallowed, so the watchers never stopped | the checkout and reconcile watchers actually stop at close | **WORKS** | `test_checkout_watcher.py` |
| M18 | Liveliness and logo worker pools are drained and joined on close | queued probes finish, and a persist is shielded | no lost liveliness dots on close | **UNVERIFIED** | `test_anyio_pools.py` |
| M19 | `utils.sfx.release()` on teardown; `close_http_client()` and `db_manager.close()` share one suppress | the HTTP close failing used to skip the DB write | history and favourites are written on close even if the HTTP client fails | **WORKS** | `test_sfx.py` |

---

## Part 2: Services

### 2.1 Licensing and premium: what the revert actually achieved

The user asked for everything licensing and premium to go back to 2.2.0. `2bee4e1` made `kiri_license.py`, `license_token.py` and `premium_service.py` byte-identical to 2.2.0. **That was true at that commit and is not true at HEAD.** Three later commits added changes back on top.

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| L1 | `LicenseUnavailable` gained `status_code` and `is_refusal` | so the watcher can branch on the answer | none directly | **WORKS** | `test_checkout_watcher.py::test_hard_refusal_aborts_the_watcher_after_one_poll` |
| L2 | **The checkout watcher ABORTS on HTTP 402/403** | the Worker runs on the free KV tier (1,000 writes/day); a 5s poll across the window burns ~180 writes per checkout | **In 2.2.0 the watcher kept polling for the full 15 minutes on any error. At HEAD, a 402 or 403 during the post-payment window makes it give up instantly, and premium never unlocks automatically. If the server transiently returns 403 because the entitlement has not propagated yet, 2.2.0 would have recovered and HEAD will not.** | **BREAKS (conditional)** | `test_checkout_watcher.py::test_hard_refusal_aborts_the_watcher_after_one_poll` |
| L3 | The checkout watcher sleeps with jitter plus exponential backoff (5s to 40s) | same KV-budget rationale | the unlock lands up to ~40s later and less predictably | **UNVERIFIED** | `test_checkout_watcher.py::test_watcher_polls_pending_then_unlocks_and_notifies` |
| L4 | New system notifications for premium unlock and premium loss | the toast is invisible when the app is backgrounded | two new shade entries. **The state flip itself is pre-existing 2.2.0 behaviour. What is new is that a transient licence hiccup that used to silently drop you to free now announces it.** | **UNVERIFIED** | `test_notifications.py::test_revoke_announces_once`, `::test_relock_then_revoke_announces_again` |

**What 2.3.0's licensing hardening proposed and the revert correctly dropped.** These are the changes that are *not* on HEAD, and each one is a genuine 2.2.0 weakness:

| Dropped 2.3.0 item | 2.2.0 behaviour that survives on HEAD |
|---|---|
| `kiri_license.py` excluded HTTP 400 from `status_refusal` | **HEAD keeps 2.2.0's `code in (400, 402, 403, 404)`. A 400 from the server still revokes a standing unlock.** |
| A central `_revoke()` clearing memory and the stored token | a revoked licence re-unlocks on the next boot; a revoke lasts exactly one session |
| `effective_unlocks(claims)` predicate | inline equivalent, no single named predicate |
| Catalog payload validation | a malformed catalog raises a generic error rather than a catchable `LicenseUnavailable` |
| Checkout email/product pre-validation, amount guard | an invalid email is sent to the server |
| Per-phase 4-tuple `_LICENSE_TIMEOUT` (pool 3.0s) | HEAD uses a scalar 15.0s, so pool acquisition can wait 15s |
| One immediate retry on a transient licence failure | a single timeout surfaces to the user instead of self-healing |
| `license_token.py` (the verifier) | **byte-identical to 2.2.0. No signature bypass exists in either version. No change at all.** |

Note the stale comment at `src/core/constants.py:215-217`: it claims the licence service builds an explicit 4-tuple timeout. It does not. The comment survived the revert because `constants.py` was not reverted with it.

**Recommendation for the re-plan:** the 400-revokes behaviour is the one item here that is arguably a bug rather than a design choice, and it is 2.2.0 behaviour. It should be re-applied as a deliberate, separately tested change, not smuggled in with a notification feature.

### 2.2 System notifications (the only genuinely new feature surface in 2.3.0)

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| N1 | `src/services/notify_service.py`, a new 240-line module wrapping `flet_notifications.LocalNotifications`. Two channels (`ktv_feedback` silent, `ktv_channel` default), four reserved ids (4100 feedback, 4101 channel online, 4102 scan, 4103 update) | the whole feature | new shade entries across the app | **UNVERIFIED on device** | `tests/test_notifications.py` (28 tests) |
| N2 | The CI manifest patch: `uv run flet-notifications-patch --project-root build/flutter` in both the APK and AAB jobs | **Neither Flet nor flet-notifications declares `POST_NOTIFICATIONS`. Android 13+ silently drops every notification without it. The three notifications that already shipped were dead on a modern phone while passing every Windows test.** | **This step is the enabling condition for every notification in this release.** Without it the whole feature is invisible on Android 13+. | **UNVERIFIED** | none. The AAB job verifies `supportsPictureInPicture` in the manifest but **not** `POST_NOTIFICATIONS`. |
| N3 | The patcher's desugaring injection pinned `desugar_jdk_libs` 2.1.4, shadowing the 2.1.5 the workflow's own sed would install | the patch runs first | the Android build now uses the intended desugaring version | **REVERTED** (fixed in `522de77`) | none |
| N4 | Screenshot saved posts a notification | the native fullscreen route draws no Flet tree | a notification confirms the screenshot | **UNVERIFIED** | not at this call site |
| N5 | Favourite added or removed posts a notification | same; the star's green colour is invisible in native fullscreen | a notification on every favourite toggle. **The star still flips to green in-app. The notification is additive, not a replacement.** | **UNVERIFIED** | `test_notifications.py::test_feedback_posts_on_the_silent_channel` |
| N6 | "Channel is back online" notification with a `ktv://play?url=` deep link | liveliness recovery was silent | a shade entry when a dead channel comes back | **UNVERIFIED** | `test_notifications.py::test_recovery_posts_on_the_alert_channel_with_a_deep_link` |
| N7 | "Premium unlocked" / "Premium ended" notifications | the toast is invisible when backgrounded | two shade entries | **UNVERIFIED** | `test_notifications.py::test_revoke_announces_once` |
| N8 | "New version available" notification, latched per version and persisted | a non-mandatory update was invisible unless Settings was opened | one notification per new version | **UNVERIFIED** | `test_notifications.py::test_update_announces_once_per_version` and 3 more |
| N9 | "N new videos found" notification after a device scan | scanning is the longest local job and the one a user walks away from | a shade entry on a real gain only | **WORKS** | `test_notifications.py::test_scan_announces_only_a_real_gain` |
| N10 | "Channels updated: N new, M gone" notification after a background refresh | a tier flip refetched behind the user's back | a shade entry when the grid changes on its own | **WORKS** | `test_notifications.py::test_background_refresh_announces_the_delta` and 6 more |
| N11 | The foreground-refresh exemption is a **count**, retired in a `finally` | it began as a boolean, and the boolean leaked on any load that ended without reaching the announcement, silently suppressing the next background refresh | a background refresh still announces after a failed foreground refresh | **WORKS** | `test_notifications.py::test_the_foreground_flag_resets`, `::test_overlapping_foreground_refreshes_both_retire` |
| N12 | The notification module was imported but not committed for 43 minutes | `git add -u` does not add new files | the app would have raised `ImportError` on every boot | **REVERTED** (fixed by CI) | **none, and this is the point: the suite was green** |

### 2.3 The playlist-failure cooldown: added, then removed

| # | Change | Why | User-visible | Status |
|---|---|---|---|---|
| C1 | A six-hour per-playlist failure cooldown, a durable `playlist_failures` DB key, and three new DB methods | a dead playlist URL was refetched on every boot, and the fan-out is bounded by one 60s timeout, so a dead host could add its full timeout to every start | **none on HEAD** | **REVERTED, net zero** |
| C2 | The removal rationale, in the commit body: "an invented number and an outlier: the app's own failure-memory precedent is `_FAILED_LOGO_TTL = 300` (five minutes, in-memory, self-evicting), so six hours is 72x that and the only multi-hour negative cache in the tree." Costs: a slow-but-alive server (>20s read) was remembered exactly like a 404; no override (`force=True` never reached the playlist path, no per-playlist delete, re-adding the same URL did not clear it); silent data loss (a skipped playlist's channels vanished from the grid and the Custom dropdown with only a log line); durable DB writes for cache-class data with no pruning | | | |
| C3 | The only surviving trace: `src/database/manager.py:368` pops the leftover `playlist_failures` key on "Reset library" | scrubs residue written during the window | none | **WORKS** |
| C4 | The other half of the same commit was **kept**: the playlist is fetched before it is saved (see AC1) | "Keeps the good half of `bc163e0`" | a bad playlist URL no longer claims success | **WORKS** |
| C5 | The playlist fan-out is now bounded by an overall 60s timeout | one slow DNS plus one slow host could hold the lock indefinitely | a slow custom playlist can no longer stall the boot past 60s. When it trips, that playlist's channels are missing for that load. | **WORKS** |
| C6 | `iptv_service.fetch_playlist` now raises `PlaylistFetchError` instead of returning `[]` | the old `return []` made "failed" and "legitimately empty" indistinguishable | callers can fall back to stale cache with an honest log line | **WORKS** |
| C7 | The fetch is validated before the network call and streamed with an 8MB cap | | | **WORKS** |

### 2.4 Caching: msgpack and the sidecar

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| CC1 | `liveliness_store.py` moved from JSON to msgpack (`liveliness.mpk`) with a schema stamp, `fsync` before `os.replace`, and a one-shot legacy JSON import that deletes the old file | msgpack was a transitive-only dependency; `fsync` so a power loss cannot leave a half-flushed file | verdicts survive a restart; a corrupt store silently re-derives them (a few grey minutes) | **WORKS** | `test_liveliness_store.py` (4 tests) |
| CC2 | `src/channels/sidecar.py`, a new 116-line msgpack sidecar storing the **parsed** channel list beside each raw `.m3u8`, validated against the raw file's mtime and size, rows encoded as positional lists (measured 36% smaller than dicts) | the provider re-parsed multi-MB playlist text on every launch, on the event loop | faster cold start. The raw playlist stays the source of truth; deleting `.mpk` is harmless. | **WORKS** (the perf win is a benchmark claim, not a device measurement) | `test_sidecar.py` (8 tests) |
| CC3 | The provider now loads the sidecar first, parses off-thread, streams the fetch with a 16MB cap, and fetches the free and premium sources concurrently | | manual Refresh with no network now serves stale cache instead of emptying the grid. **A tier flip now swaps the in-memory list correctly.** | **WORKS** | `test_integration_smoke.py`, `test_app_loader.py` |
| CC4 | The provider's refresh lock is eagerly created and every caller waits on it | the v2.2.0 "if locked: sleep 0.5s and return whatever we have" shortcut served half-empty snapshots | concurrent refreshes no longer return a partial list | **WORKS** | same |
| CC5 | `provider.invalidate()` was added | to encapsulate what used to be an external poke | none | **DEAD** (no call sites) | none |

### 2.5 The anyio task-pool migration

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| AP1 | `src/services/anyio_pools.py`, a new 176-line structured-concurrency pool: bounded queue, N workers in one `anyio.create_task_group()`, `stop(drain=True)` drains then cancels and joins | the old hand-rolled `create_task` workers could neither be cancelled nor awaited | background workers shut down cleanly; no "Task was destroyed but it is pending" on exit | **WORKS** | `test_anyio_pools.py` (9 tests) |
| AP2 | **Offline liveliness now returns "unknown", not "dead"** | the old `return (url, False)` painted every dot red whenever the radio dropped | **going offline no longer turns every liveliness dot red** | **WORKS** (tested), **UNVERIFIED** on device | `test_liveliness.py::test_pool_timeout_is_unknown`; `test_liveliness_offline.py` |
| AP3 | The probe semaphore is module-level, shared by all instances | the old per-instance `Semaphore(4)` let 2 workers plus N batch callers run 8-12 concurrent probes against a 2s-timeout pool, and exhaustion painted dots red | healthy streams are no longer marked dead by local pool exhaustion | **WORKS** | `test_liveliness.py::test_semaphore_is_shared_module_level` |
| AP4 | The HEAD probe is now a streamed ranged GET that breaks early | a Range-ignoring server plus a non-streaming GET downloads the entire file into memory | **a direct-MP4 URL no longer risks an OOM during a probe** | **WORKS** | same file |
| AP5 | One `_is_live_status()` predicate replaces two ad-hoc status sets | consistency | none | **WORKS** | `test_liveliness.py::test_live_predicate_unified` |
| AP6 | `fire_batch()` removed entirely | the per-card subscription replaced it | none | **REVERTED-equivalent** | `grep` confirms no references |
| AP7 | The liveliness persist is shielded with `anyio.CancelScope(shield=True)` and re-drained on cancellation | a verdict could be lost on close | no lost dots on close | **WORKS** | `test_anyio_pools.py` |
| AP8 | `logo_cache.py` migrated to `TaskPool`; the cache dir is resolved per call; only `http`/`https` reach the client; the positive cache is checked first; a URL is not enqueued twice; sibling extensions are removed after a successful write | the old task was untracked; `file://`/`ftp://` URLs reached the HTTP client; a png-to-jpg content change left the stale `.png` shadowing the fresh `.jpg` | logos render faster (no network when cached), broken logo URLs are not retried every rebuild | **WORKS** | `test_logo_cache.py` (4 tests) |

### 2.6 HLS proxy hardening: the highest-risk area in the release

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| HX1 | **TLS verification is now ON for every origin**; the global `verify=False` is gone, replaced by per-host exemptions via `insecure_hosts` | the old global `verify=False` was MITM-able for every origin | **`src/main.py:134` constructs `HLSProxy()` with no arguments, so verification is now enforced for every upstream the proxy touches. Any stream served over HTTPS with a self-signed, expired or hostname-mismatched certificate that played fine in 2.2.0 will now fail to load. The escape hatch exists but is wired to no host, with no setting and no per-stream opt-in.** | **BREAKS (conditional)** | `test_hls_proxy.py::test_insecure_hosts_mount_logged` proves the mechanism, not that any real host works |
| HX2 | Timeouts made explicit and per-phase (`read 15s`, `write 10s`, `pool 2s`) | a scalar 20s widened pool acquisition to 20s | a saturated pool fails fast instead of hanging the player | **WORKS** | `test_hls_proxy.py` |
| HX3 | Master-playlist fetches memoised for 30s | variants plus audio double-fetched the same URL | the picker makes one request instead of two | **WORKS** | none |
| HX4 | `fetch_master` returns `(content_type, text)` and raises `PlaylistFetchError` instead of returning `None` | callers can distinguish 404 from a dead host | the picker can tell "no variants" from "host is dead" | **WORKS** | `test_hls_proxy.py` |
| HX5 | The hand-rolled server hardened: 5s read timeout, 64 header lines, 8KB header bytes, 16KB query cap, 400 on a malformed request line, 405 on non-GET | Slowloris and header abuse | none for normal playback; the proxy binds `127.0.0.1` only | **WORKS** | `test_hls_proxy.py` |
| HX6 | Custom-header injection is validated and CRLF-safe; `host`, `content-length`, `transfer-encoding`, `connection` are dropped | CRLF smuggles response splits | a stream needing a custom `Host` header now has it silently dropped | **WORKS** | `test_hls_proxy.py` |
| HX7 | Playlist-vs-segment detection is now a heuristic plus a fetch-time correction; a non-playlist body is streamed as bytes instead of served as an error page | an extension-less segment used to be served as a broken playlist | extension-less segments stream correctly | **WORKS** | `test_hls_proxy.py::test_looks_like_playlist` |
| HX8 | `#EXT-X-SESSION-KEY` is now rewritten like `#EXT-X-KEY` | it used to fall through verbatim, leaking the original key URL without a Referer | **an encrypted HLS session that used to fail now plays** | **WORKS** (tested), **UNVERIFIED** on a real encrypted stream | `test_hls_proxy.py::test_session_key_rewritten` |
| HX9 | Per-connection handler tasks are tracked and joined on stop; conditional validators are forwarded; `etag`/`last-modified`/`cache-control` are echoed back | | active segments no longer die mid-chunk on close; 304s instead of full 200s on every poll | **WORKS** | `test_hls_proxy.py` |

### 2.7 The Android bridge and its consumers

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| AB1 | `src/services/android_bridge.py`, a new 191-line shared bridge: a cached but **revalidated** activity lookup, memoised `SDK_INT`, a per-attribute activity probe, a TV/leanback probe with a 5s retry TTL for an unknown verdict | the old write-once global served a dead Activity forever after a rotation or a PiP return, and the `getattr(a) or getattr(b)` form skipped the second attribute whenever the first **raised** | PiP, TV detection, MediaStore and screenshots stop depending on a stale Activity reference | **UNVERIFIED** (the module itself carries a "Needs-hardware-confirm" banner) | `test_android_bridge.py` (5 tests) |
| AB2 | `pip_service.enter_pip()` now returns the **system's** verdict instead of always `True` | so "the system said no" is distinguishable from "we called it" | none unless a caller checks | **UNVERIFIED** | `test_deep_link_pip_fixes.py` |
| AB3 | `pip_service.set_auto_pip()` returns `False` below API 31 instead of `True` | the old no-op-True made unsupported look armed | none unless a caller checks. **The player-side caller was not audited against the new contract.** | **UNVERIFIED** | needs review |
| AB4 | `pip_service` rejects `aspect=0` explicitly and builds the ratio with `Fraction(int(x*1000), 1000).limit_denominator(239)` | `Fraction(16/9)` bakes in the binary float error | none | **UNVERIFIED** | n/a |
| AB5 | `tv_detect.py` becomes a 23-line shim over the bridge | consolidation | TV detection gains the unknown-retry TTL | **UNVERIFIED** on a TV | `test_android_bridge.py::test_is_tv_false_off_device` |
| AB6 | `device_info.py` uses per-field fallbacks and logs once without a traceback | one bad getter dropped the whole line; `exc_info=True` polluted the log dump being diagnosed | the Settings device panel is more robust | **WORKS** (desktop path) | none |

### 2.8 Local scanner

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| LS1 | **MediaStore discovery rewritten**: named column indices, the `_data` column dropped entirely on API 29+, the `os.path.exists` gate removed, a `content_uri` built for every row, `duration` and `mime_type` captured, ID-only rows grouped under one "Device Videos" folder, an explicit `java.lang.String[]` projection | the `_data` column is deprecated since API 29 and unreadable on 30+; a raw Python list throws `Invalid arguments` inside PyJNIus and is silently swallowed, which **was** the cause of the empty library | **on Android 10+ the Local tab lists device videos instead of showing an empty library** | **UNVERIFIED** (hardware only) | `test_local_scanner.py::TestPhase6ScannerIds` (6 tests) |
| LS2 | `delete_media_store_video` returns a tri-state `True`/`False`/`None`, where `None` means "consent needed" | the old False-everything forced callers to guess between retry-with-consent and give-up | deleting another app's video takes the Android consent path instead of failing silently | **UNVERIFIED** | `test_media_store_consent.py` (4 tests) |
| LS3 | `resolve_saf_path` no longer echoes an unresolvable `content://` URI; uses `posixpath`; rejects `..` after normalisation | callers would mistreat a URI as a filesystem path | picking an SD-card folder no longer produces a bogus path that fails later | **WORKS** | `test_local_scanner.py` |
| LS4 | **Default scan paths narrowed**: on POSIX desktop only `Movies/Videos/Downloads/DCIM` are scanned (the whole-home walk is gone), and on Android the Termux home directory is no longer appended | "NEVER the whole home tree (slow, battery-heavy, privacy-invasive)" | **Windows desktop is unchanged. Linux/macOS desktop is narrower. On Android, videos in `~/Movies` inside Termux need the manual folder picker.** | **UNVERIFIED** | `test_local_scanner.py::test_default_paths_never_whole_home` |
| LS5 | The O(n^2) duplicate scan replaced by a seen-set; walk errors are logged, not swallowed; the MediaStore merge preserves `content_uri` on the retained row | otherwise deleting a merged row falls back to a blocked file delete | faster scans, no swallowed errors | **WORKS** | `test_local_scanner.py::test_norm_key_dedupes` |

### 2.9 Thumbnails, permissions, updates, and the rest

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| T1 | The thumbnail cache key uses ms-precision mtime plus an absolute normalised path, hashed | the old `:.0f` truncation collided edits within a second | **all existing cached thumbnails are invalidated once**; after that, re-edits within the same second work | **WORKS** | `test_video_thumbnails.py` |
| T2 | The extraction bound and in-flight dedupe moved to module scope | the old per-call semaphore let two overlapping prewarms race the same `.tmp` | no more corrupt thumbnails from a rename race | **WORKS** | same |
| T3 | `prewarm_thumbnails` returns `(filled, total_available)` | the old docstring lied | none | **WORKS** | `test_video_thumbnails.py::test_return_tuple_semantics` |
| T4 | The thumbnail cache is capped at 500 files, plus orphan `.tmp` purging | unbounded growth on long-lived TV boxes | **a library over 500 videos re-extracts the oldest frames each cycle** | **WORKS** | `test_video_thumbnails.py::test_purge_bounds_growth` |
| T5 | `_extract_sync` hardened: atomic `os.replace` instead of the boolean `File.renameTo`, retry at frame 0 for sub-second clips, no `.tmp` left by a failed extraction | a silent rename failure left a cache entry pointing at a file that was never created | sub-second clips get a thumbnail; no broken images | **UNVERIFIED** (Android path) | `test_video_thumbnails.py` |
| PM1 | `request_storage_permission()` returns `"granted"`/`"denied"`/`"permanent"` instead of a bool | the old code returned `True` when nothing was granted, telling callers to scan when Android had said no | the Local tab can distinguish "ask again" from "go to Settings" | **WORKS**, **UNVERIFIED** on Android 13/14 | `test_permission_service.py` (6 tests) |
| PM2 | The permission request is SDK-aware (API 33+ asks `VIDEOS`, below that `STORAGE`, iOS `PHOTOS`) and never re-prompts a granted permission | 2.2.0 asked for a permission that does not exist on 13+, producing a confusing extra prompt | the user is asked for the right permission once | **WORKS**, **UNVERIFIED** on hardware | same |
| PM3 | The `PermissionHandler` is reused rather than re-created per call | a per-call service leak, and a request before the native binding existed could silently fail | fewer native instances | **WORKS** | indirect |
| U1 | Announcements now deliver on the same build | the old gate returned `None` before reaching the announcement branch, so notices never displayed | a publisher can post an announcement on the current build | **WORKS** | `test_update_service.py::test_same_build_announcement_delivers` |
| U2 | `mandatory` is parsed explicitly | `bool("false") is True` | **a publisher sending `"mandatory": "false"` no longer forces the update dialog on every user** | **WORKS** | `test_update_service.py::test_string_false_mandatory_is_not_mandatory` |
| U3 | `check_for_update` returns an `UpdateInfo` dataclass | attribute access, unambiguous contract | none | **WORKS** | `test_update_service.py` |
| U4 | The check is cached for 5 minutes and the config URL must be https | do not hit the network on every Settings open | the Check button within 5 minutes returns the cached verdict | **WORKS** | `test_update_service.py::test_non_https_config_rejected` |
| AD1 | `ad_service.close()` awaits the cancelled retry task | so app close never tears the loop down under an unwinding retry sleep | no "Event loop is closed" error on close | **WORKS** | `test_premium.py` |
| HC1 | The shared httpx client gained HTTP/2, a default `User-Agent`, a lock and connect-retries | h2 collapses same-origin fetches onto one connection | faster first byte on multi-asset screens. **Some hosts that saw a `python-httpx` UA now see a browser UA, which can change server behaviour in either direction.** | **WORKS** | `test_http_client.py` (6 tests) |
| HC2 | The YouTube resolver gained an explicit 4-tuple timeout, HTTP/2 and a UA | a scalar 15s widened pool acquisition | YouTube live channels resolve faster. **This is the one place a UA change touches a third-party service that actively fingerprints clients. It deserves a device check.** | **UNVERIFIED** | none |
| LV1 | `liveliness.set_on_change` replaced by `add_on_change`/`remove_on_change` subscriber lists; true LRU; bounded dirty queue | the old single slot meant mounting Search froze Home's dots, and unmounting never restored them | Home, Search and the grid can each listen without clobbering each other | **WORKS** | `test_liveliness.py` (7 tests) |
| N1 | `channels/normalize.py`: legacy country names canonicalised, acronyms preserved, `NON_COUNTRY_GROUPS` expanded from 14 to 24 with a precompiled regex, premium `country_code` set to the real ISO code | naive title-casing split saved filters; a bare 2-3 letter tvg-id suffix is not a country | the country folder is "Nigeria" not "nigeria". Premium channels are findable by country code. **A user who manually picked a country filter with different spelling would find it matching nothing until re-picked.** | **WORKS** (intended case), **UNVERIFIED** (saved-filter edge case) | `test_channel_pack.py` |
| N2 | `src/utils/history.py`, a new shared 82-line helper | both views previously duplicated the logic and got it wrong the same way | titles and logos resolve consistently | **WORKS** | `test_recently_watched.py`, `test_utils.py` |

---

## Part 3: Core, screens, database, utils and build

### 3.1 `src/core/app_loader.py`

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| AL1 | The background-refresh notification (see N10) | | | **WORKS** | `test_notifications.py` |
| AL2 | Per-playlist fault isolation (`_safe_fetch`) | one bad custom playlist must not abort the whole load | one dead playlist no longer blanks the grid | **WORKS** | `test_release_audit_fixes.py::test_app_loader_isolates_unexpected_fetch_errors` |
| AL3 | `force=True` no longer clears the provider's in-memory list | clearing first would serve `[]` to concurrent readers mid-fetch | a force-refresh no longer momentarily empties the grid | **UNVERIFIED** | none |
| AL4 | Merged entries are shallow copies | mutating the provider's dicts in place leaked `is_custom` into durable storage | custom channels no longer acquire `is_custom: True` in the stored JSON | **UNVERIFIED** | none |
| AL5 | An empty result keeps the stale state and shows an error toast | an empty success must not wipe a good grid | an offline refresh no longer replaces the grid with an empty list | **UNVERIFIED** | none |
| AL6 | Playlist rows with a missing URL are skipped | a corrupt row raised `KeyError` inside the gather | a corrupt row no longer kills the load | **UNVERIFIED** | none |
| AL7 | **Flat-playlist group names use a hyphen, not an em dash** | ASCII safety | **the folder name in the Custom dropdown changes. A favourite saved under the old em-dash group no longer matches the `(group, name)` key and falls back to the bare-name match, which can remap to a different regional variant of a same-named channel.** | **BREAKS (minor)** | none |
| AL8 | `_reconcile_favorites` prefers same-group matches and de-duplicates | duplicate names across groups remapped to the wrong regional variant | favourites re-key to the right regional channel; no duplicate stars | **UNVERIFIED** | none |

### 3.2 The rest of `src/core/`

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| K1 | The changelog is newest-first with a 2.3.0 entry and a `latest_version()` | 2.2.0's fallback used `next(reversed(...))` over an oldest-first dict, so an unknown version showed the **2.0.6** notes | the dialog's "what's new" shows 2.3.0's notes | **WORKS** | `test_theme.py::test_fallback_returns_latest_not_oldest` |
| K2 | The crash directory is anchored to the app root, not the CWD | | crash logs always land in the same place | **WORKS** | `test_theme.py::test_record_crash_returns_path_and_preserves_cause` |
| K3 | Crash filenames are collision-proof, the count is bounded, and the original exception is preserved | two crashes in the same microsecond could overwrite each other | no crash log is ever silently lost | **WORKS** | `test_theme.py` (2 tests) |
| K4 | `install_crash_handler` is idempotent | re-install replaced `on_error` repeatedly | none | **WORKS** | `test_theme.py::test_install_crash_handler_idempotent` |
| K5 | The deep-link parser gates on scheme and netloc at the function, not only at the call site | "it used to accept `https://evil.com?url=`" | a hostile `https://` route can no longer be parsed into a playable URL | **WORKS** | `test_url_validator.py::TestPhase4DeeplinkGates` |
| K6 | External deep links are network-only (`http`, `https`, `rtsp`, `rtmp`); `file://` and `content://` are refused | "a malicious link could otherwise make the app open arbitrary local files" | a `ktv://` link to a local file is refused. Local files still play from inside the app. | **WORKS** | `test_url_validator.py::test_file_url_rejected_from_external_link` |
| K7 | Base64 decode is strict and size-capped (8192 chars) | a 10MB query param must never reach `b64decode` | a huge `url=` param is rejected instead of freezing the app | **WORKS** | `test_url_validator.py::test_oversize_field_rejected` |
| K8 | A title is only base64-decoded when it round-trips | the old rule misdecoded any alphanumeric plaintext that happened to be valid base64 | a plain-text title now shows the title | **WORKS** | `test_url_validator.py::test_plaintext_title_not_misdecoded` |
| K9 | Deep-link headers are validated and blocklisted (`host`, `content-length`, `transfer-encoding`, `connection`, `authorization`, `cookie`) | those must never ride in from an external link | a link smuggling `Authorization` has it dropped; **the stream may then fail to play if it required them** | **WORKS** | `test_url_validator.py::test_blocked_header_dropped_others_kept` |
| K10 | The memory log buffer is per-instance and locked; timestamps gained the date | class-level shared state | the Activity Terminal shows the date | **WORKS** | `test_theme.py::test_memory_handler_locked_roundtrip` |
| K11 | **The root log level default dropped from DEBUG to INFO** | a new `KTV_LOG_LEVEL` env var | **the Activity Terminal now shows INFO and above only, where 2.2.0 showed DEBUG. The in-app log viewer is markedly less detailed.** | **BREAKS** | `test_theme.py::test_setup_logging_reconfigures_level` pins the new behaviour |
| K12 | `_ShutdownSafeStreamHandler` replaces the global `logging.raiseExceptions = False` | scoped so a handler bug elsewhere still surfaces | no "Logging error" trace on shutdown | **WORKS** | `test_theme.py` |
| K13 | Per-library log-level overrides removed (`flet_controls`, `flet_transport`, `kivy.jnius`, `jnius`) | let the root level govern | these libraries now log at INFO through the console | **UNVERIFIED** | none |
| K14 | `AppState` is a dataclass; the `theme_mode` field is removed; `channels_hash` is an order-sensitive SHA-256 hex | the old `sum(hash(...))` was commutative, so a reshuffled playlist produced the same hash and every memo kept serving the old folders | **a reordered or renamed playlist now refreshes the grid and the filter pills. In 2.2.0 it did not.** | **WORKS** | `test_release_audit_fixes.py::test_channels_hash_is_order_sensitive` and 2 more |
| K15 | `update_data` is typed `UpdateInfo` | unambiguous contract | none | **WORKS** | `test_header.py` |
| K16 | `add_to_history` uses a single assignment and a safer title fallback | fewer observable notifications per write | a re-played stream with no new title keeps its old title | **WORKS** | `test_state.py` (5 tests) |
| K17 | `reset()` clears the deep-link flag | it was left set after a reset | a subsequent launch is not treated as a deep-link launch | **WORKS** | `test_release_audit_fixes.py::test_state_reset_clears_deep_link_flag` |
| K18 | `AppColors.is_dark` is public with a shared fallback; dead theme helpers deleted | 2.2.0's `grey_dim()` no-page fallback returned light grey while `_is_dark()` returned dark | the two can no longer disagree | **WORKS** | `test_theme.py::test_grey_dim_agrees_with_is_dark` |
| K19 | `on_secondary` changed from BLACK to WHITE in both schemes | measured WCAG: black 5.13:1, white 4.10:1 on the accent | **text and icons on the accent change from black to white. Normal-size text now measures 4.10:1, below the 4.5:1 AA threshold.** The code comment states the trade-off knowingly. | **BREAKS (accessibility, knowingly accepted)** | `test_theme.py::test_on_secondary_is_white_both_schemes` |
| K20 | Both themes gained `scaffold_bgcolor`, `dialog_theme`, `appbar_theme`; desktop transitions pinned to ZOOM | | dialogs and app bars pick up the theme surface colour | **WORKS** | `test_theme.py::test_themes_carry_scaffold_dialog_transitions` |
| K21 | The `SPACE_*` and `RADIUS_*` aliases were removed from `tokens.py` | so renames fail loudly at import time | none in-repo | **WORKS** | `test_theme.py::test_no_space_radius_aliases` |
| K22 | The type scale changed: `FONT_MD` 13 to 12, `FONT_LG` 15 to 16, `SPACING_MD` 14 to 12; `BORDER_RADIUS_FULL` 9999 to 999 | 4pt grid; 9999 risks a rounding overflow | **body text in pills is one pixel smaller; a slight tightness change in padded rows** | **WORKS** | `test_theme.py::test_spacing_grid_and_fonts` |
| K23 | `is_valid_play_url` is public with a compat alias; control characters, stray whitespace, `..` traversal, bare drive roots and embedded credentials are all rejected | paste artifacts, SSRF obfuscation, phishing-prone credential URLs | **`http://example.com@evil.com/` is now refused outright, so a legitimate stream URL with embedded HTTP Basic credentials will fail at validation instead of at connect.** | **BREAKS (possible)** | `test_url_validator.py::TestPhase4ValidatorHardening` (7 tests) |
| K24 | Windows drive paths accept a forward slash; a bare drive root is refused; protocol-relative URLs are not local files | | `C:/Videos/movie.mp4` now plays (2.2.0 refused it); `C:/` alone is refused | **WORKS** | `test_release_audit_fixes.py::test_path_branch_acceptance` |
| K25 | **The `file://C|/Windows/...` pipe-separator bypass is fixed** | the pipe drive form split to `['c|', 'windows', ...]`, matching neither a bare drive root nor the colon-written blocklist entries | the pipe form is now rejected exactly like the colon form | **WORKS but UNTESTED** (the only security fix in this release with no automated pin) | **none** |

### 3.3 Screens

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| SC1 | The Premium purchase UI reads `getattr(page_obj, "premium", None)`, and `main.py` mirrors the service onto the page | `main.py` built `PremiumService` and stored it on the controller but never on the page, so `_load_license` returned at its first guard and the products, checkout and recovery ID never rendered | **BREAKS (fixed): in the intermediate 2.3.0 state the Premium section showed a heading and a description but no purchase buttons at all.** | **WORKS** | `test_env_toggle.py` |
| SC2 | The Premium listener uses `use_effect` with a cleanup rather than `ft.on_mounted` returning a cleanup | the installed Flet's `use_effect` takes cleanup as the third argument | the Premium row updates live and the listener no longer leaks | **UNVERIFIED** | none |
| SC3 | The "Could not reach the license service" row is now shown only on a real error, with a **Retry** button; a separate busy state shows a spinner | 2.2.0 showed the error whenever the product list was empty, **including on the very first paint while the request was still in flight** | **opening Settings no longer shows a false error.** This one is not a 2.3.0 regression; it is a 2.2.0 lie that 2.3.0 fixed. | **WORKS** | `test_settings_screen.py::test_phase7_source_contracts` |
| SC4 | The checkout URL must be HTTPS; an empty recovery ID is refused | defensive | a bad checkout URL aborts with a warning | **UNVERIFIED** | none |
| SC5 | The Premium subtitle reads claims via a guarded `getattr` | | the row renders even if the licence service is missing | **WORKS** | `test_settings_screen.py` |
| SC6 | The log viewer uses the instance handler, caps the dump at 500 lines with an "older lines omitted" marker, and updates the dialog's own control | a long session janked low-end TV boxes; `page.update()` from a dialog does not reliably repaint it | the log viewer is bounded and does not freeze a TV. **The section is renamed from custom-content management to "Development."** | **WORKS** | `test_settings_screen.py` |
| SC7 | The theme switch is reactive (local state, not the dead `_theme_mode`) | removing the local mirror made the icon and switch lag | the switch and the theme flip in the same frame | **WORKS** | `test_release_2_3_0_regressions.py::test_theme_toggle_sets_local_state` |
| SC8 | The country dialog is searchable and bounded | component state cannot reach the shown instance | you can type to filter the 177-country list | **WORKS** | `test_settings_screen.py` |
| SC9 | A failed country save is reported | the exception was swallowed by a bare except | the user is told instead of the save silently failing | **UNVERIFIED** | none |
| SC10 | Empty ad banners are filtered out of Settings | `build_banner_ad` returns a 0x0 placeholder | no invisible spacer rows | **WORKS** | `test_settings_screen.py` |
| SC11 | The version row guards the no-op controller default | the default is a silent no-op off-shell | a dead-looking row explains itself | **WORKS** | `test_settings_screen.py` |
| SC12 | The Settings brand mark is no longer tinted | the SVG is blue line-art | the icon renders in its real blue | **WORKS** | `test_header.py::test_brand_mark_no_tint_and_error_fallback` |
| SC13 | About links fail visibly | the old code awaited the launcher with no error handling | a failed tap warns | **UNVERIFIED** | none |
| SC14 | All remaining `asyncio.create_task` removed from Settings | tasks scheduled outside the page loop die with the view | Clear History and Reset Library no longer silently do nothing | **WORKS** | `test_settings_screen.py` |
| SC15 | "Reset library" marks the refresh as foreground | | one toast, not a toast plus a shade entry | **WORKS** | `test_notifications.py` |
| SC16 | Onboarding: the loading flag starts from `prober is not None`; a probe error state; a "No countries found yet" branch with Retry; the country list is a flat capped Column; an `is_saving` guard; hint text under the button | the old empty-country branch rendered "Connecting..." forever; a nested `ListView` trapped the D-pad | a retryable error state instead of an infinite spinner. **A 201st+ country would be unreachable. With 177 countries this is not hit.** | **WORKS** | `test_settings_screen.py::test_onboarding_source_contracts` and 3 more |
| SC17 | The Recently Watched screen no longer renders the raw URL | "stream URLs commonly contain user:pass@ credentials" | **2.2.0 printed `http://user:password@host/stream` in plain text. Credentials no longer appear on screen.** | **UNVERIFIED** (no test asserts the URL is absent) | none |
| SC18 | The Recently Watched AppBar moved onto the `View`; the screen takes explicit `page` and `on_back` props; a "Browse channels" empty-state CTA | the AppBar inside the Column got no route-integrated back | the screen gains a title bar and a back arrow | **WORKS** | `test_recently_watched.py` |
| SC19 | Local screen: per-mount service singletons; a scan generation counter; background failures keep the old grid; `_safe_task` for every background job; custom-path preferences validated; `resolve_saf_path` failure reported; folder picking blocked gracefully on web | constructing services per scan leaked a duplicate registration; a bare `create_task` dropped failures silently | no duplicate service registration; a failed post-delete refresh no longer blanks the library; failures are logged instead of vanishing | **UNVERIFIED** (only 2 smoke tests exist) | none |
| SC20 | The Android delete flow: tri-state result, 40 polls at 0.5s, a progress row while waiting | the answer arrives when the user taps Allow, not when the dialog opens, so a fixed pause reported "Android kept a copy" for deletes that had succeeded | a successful delete is no longer misreported as failed | **UNVERIFIED** (the platform part) | `test_media_store_consent.py` |
| SC21 | The Local screen has a tri-state permission empty state with "Grant Access" / "Open Settings" | | an actionable message instead of an endless "Scanning device..." | **WORKS** | `test_permission_service.py` |
| SC22 | Search: the screen-level liveliness subscription is removed; local-file search matches the file stem; the search field border kwargs were fixed; the button and Enter flush the field immediately; auto-scan is cancelled on unmount; the pager is shared with the grid; the local subtitle is the basename | a broken border argument crashed the screen; the magnifier set the query to the value it already held | **the Search screen could fail to open in 2.3.0; at HEAD it opens.** Typing `c` in the Local-files tab no longer returns every file under `C:\`. | **WORKS** | `test_release_2_3_0_regressions.py::test_search_button_uses_field_value_not_state` |

### 3.4 `src/database/manager.py`

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| DB1 | A `SCHEMA_VERSION` key is written | | the stored JSON gains a field. **No migration is actually implemented; `_validate_loaded` does not branch on it.** | **WORKS** | `test_database_manager.py` |
| DB2 | No I/O in `__init__` | importing must not create directories | none | **WORKS** | same |
| DB3 | `db_path` is honoured | it was ignored | test isolation improves | **WORKS** | same |
| DB4 | **Corruption recovery: quarantine plus backup fallback** | 2.2.0 renamed the corrupt file to a single fixed `.json.corrupted` (overwriting earlier forensics) and returned `{}` **without trying the backup** | **2.2.0: a corrupt main store meant a completely empty app (favourites, history, playlists, settings all gone) even when a valid backup existed. At HEAD the backup is restored.** | **WORKS (weakly)** - the test asserts only `_data is not None` | `test_database_manager.py::test_corrupt_file_handling` |
| DB5 | Legacy row migration and validation | one corrupt row used to crash every reader | a corrupt row is dropped, the rest loads | **UNVERIFIED** | none |
| DB6 | Atomic writes with `fsync`, a temp file in the storage dir, a `.json.bak` copy | a crash mid-write used to truncate the store | history and favourites survive a crash mid-write | **UNVERIFIED** | none |
| DB7 | `anyio.to_thread` instead of `asyncio.to_thread` | consistency | none | **WORKS** | n/a |
| DB8 | `set_setting` stores any type, not `str(value)` | structured settings | **a value stored as an int or bool is now written as a JSON int or bool. Any reader that assumed a string now gets a non-string.** | **BREAKS (possible)** | `test_database_manager.py` covers a string only |
| DB9 | `add_playlist` and `add_custom_channel` return a bool; `remove_favorite` returns a bool and no longer writes on a miss; `remap_favorite_url` merges instead of duplicating; read methods return copies; write methods return a bool | | the same channel is no longer starred twice after a playlist swap | **UNVERIFIED** | none |

### 3.5 `src/utils/`

| # | Change | Why | User-visible | Status | Test |
|---|---|---|---|---|---|
| U1 | `toggle_favorite` became synchronous and returns the task; `toggle_favorite_async` awaits the DB write and re-reads `state.favorites` | the old code checked `_in_flight` *inside* the coroutine, so two rapid taps both passed and both ran; the snapshot assignment could clobber a concurrent toggle | **double-tapping a star toggles once, not twice and not zero** | **UNVERIFIED, and the only in-scope change with no test at all** | **none** |
| U2 | The toast-hide task is declared at module level in `utils/notifications.py` | without it the assignment created a *local* variable, so the pending hide task was never tracked or cancelled | **a new toast now cancels the previous toast's 3-second hide timer** | **UNVERIFIED** | none |
| U3 | `sfx.py` uses a single lazy `ToneGenerator` on `STREAM_MUSIC` at volume 60, with a public `release()` | per-tap construction was the documented anti-pattern; `STREAM_SYSTEM` is muted on TV, which is exactly where the clicks matter | **the confirmation click is louder on TV and no longer risks a native crash under rapid taps** | **WORKS** | `test_sfx.py` (3 tests) |
| U4 | `theme_utils.py` holds the pending save task and cancels it on a new toggle | the same missing-reference class of bug as the toast timer | **toggling twice quickly leaves the app in the mode you last chose** | **UNVERIFIED** | none |

### 3.6 Build, CI and dependencies

| # | Change | Why | User-visible | Status |
|---|---|---|---|---|
| CI1 | **Every build is now published as a pre-release and is never "Latest"** | `5ae8072` hardcoded `make_latest: true`, so a tag push published a full Latest-listed release and users could download a defective build from the default release page | **a release that is not manually promoted is invisible to the "Latest" download button on the GitHub releases page, and possibly to the in-app update flow** | **WORKS** |
| CI2 | The CI version defaults were corrected to 2.3.0 / build 21 | a manual dispatch would have built a 2.2.0-labelled artifact from 2.3.0 source | | **WORKS** |
| CI3 | The `flet-notifications-patch` step in the APK and AAB jobs (see N2) | | | **UNVERIFIED, the highest-risk item in the release** |
| CI4 | The `desugar_jdk_libs` sed normalises 2.1.4 back to 2.1.5 after the patch | the patch runs first and would shadow the workflow's own sed | | **REVERTED** (fixed) |
| CI5 | The CI pubspec-patching approach for the `jni` override was **removed**; the override moved to `pyproject.toml` | "flet regenerates pubspec.yaml on every invocation, so a post-build patch is wiped by the next build" | net zero for CI; the override is now applied at the source | **REVERTED** (the CI variant) |
| CI6 | **The `jni` dependency override moved to `[tool.flet.flutter.pubspec.dependency_overrides]`** | flet's generated pubspec pins `jni: 1.0.0` but `jni_flutter 1.0.4+1` requires `^1.1.0`, so the Dart compile fails on **every** platform | **without the override the Dart compile fails on every platform. This is a pub.dev drift fix: it will break again the next time `jni_flutter` moves.** | **WORKS** |
| CI7 | **`media_kit_libs_windows_video` declared in `[tool.flet.flutter.pubspec.dependencies]`** | the generated lock had no Windows native player library, so the Windows video surface rendered as a blank white rectangle while the Flet overlay still showed | **this is the Windows white-screen fix at the build layer** | **WORKS** |
| DP1 | `anyio>=4.0`, `flet-notifications>=0.1.4`, `msgpack>=1.0` added to dependencies | the worker-pool architecture, the notification feature, the binary caches | **the app now depends on a third-party notification package published eight days before this release.** | **UNVERIFIED** on device |
| DP2 | `pytest-xdist` added; the suite runs with `-n auto`; `RuntimeWarning` and `pytest.PytestDeprecationWarning` are errors | parallel, warning-free runs | **the suite now runs in parallel, which can expose order-dependence; and any un-awaited coroutine now fails the build** | **WORKS** |
| DP3 | Ruff extended with `B`, `RUF`, `SIM`, `UP` | bugbear found a real toast-timer bug this cycle | none | **WORKS** |
| DP4 | `version.json` is gitignored and untracked | it must not be committed before the Play build is on the store | | **WORKS** |
| AS1 | `src/assets/icon.svg` changed (a self-adapting SVG for the README) | | the README asset changed | **UNVERIFIED** |
| AS2 | `src/assets/icon_white.svg` was added, then **restored byte-for-byte** from `385abd8^` (blob `31653837fa47ab288673416052ffd44153f4a98b`, 882 bytes, 28 lines) | the new one was broken | the original file is back, byte-for-byte | **WORKS** (verified by hash) |

---

## Part 4: The re-planning worksheet

This is the working list for the next session. Each row is a decision to make deliberately, in order, before anything is re-applied on top of 2.2.0.

### Tier 1: Ship-blocking risks. Decide these first, on your own playlist, not from code.

| ID | Change | Risk if kept blind | Decision |
|---|---|---|---|
| HX1 | HLS proxy TLS verification ON for every host | channels that played in 2.2.0 fail to start on any host with a bad certificate | |
| L2 | The checkout watcher aborts on 402/403 | "I paid and premium never unlocked" | |
| CI3 | The `flet-notifications-patch` CI step | every notification is dead on Android 13+ and looks like the feature simply does not work | |
| LS1 | The MediaStore rewrite | the Local tab is empty or mis-grouped on Android 10+ | |
| AB1 | The shared Android bridge | PiP or TV detection silently dead on the target APK | |
| LS4 | The narrowed default scan paths | videos in `~/Movies` on the phone disappear from the Local tab | |
| PM1/PM2 | Tri-state, SDK-aware permissions | the Local tab prompts for the wrong permission, or never prompts | |
| K23 | Credentials in stream URLs are now refused | a stream with embedded Basic auth fails at validation | |

### Tier 2: Behaviour changes you should consciously accept

| ID | Change | What the user notices |
|---|---|---|
| K19 | White on the accent instead of black | lower contrast on the accent, 4.10:1 |
| K11 | Log level INFO instead of DEBUG | the in-app log viewer is far less detailed |
| M6 | Player-scoped error suppression | more error toasts during playback |
| AL7 | Em dash to hyphen in flat-playlist group names | a saved favourite may remap to a different regional channel |
| FB1 | The country menu's "All Countries" | dismissing the menu now goes to all, not to your default country |
| FB6 | Taller filter pills | a visible Home layout change |
| G2 | Mid-grid banner ads removed | **revenue-visible** |
| DB8 | `set_setting` no longer stringifies | a reader assuming a string gets a non-string |
| K25 | `file://C|/...` rejected | correct, but untested |

### Tier 3: Straight improvements worth keeping. Low risk, clearly good.

| ID | Change | Note |
|---|---|---|
| AL7' | Group-name normalisation (the canonical country form) | with the em-dash removal re-applied deliberately |
| G1' | Plain expanding scrolling `Column` for the grid | **and pin it with a test this time** |
| M5 | Lifecycle saves on `e.state` | fixes a real 2.2.0 bug: resume position was never saved |
| M7 | Single shared close guard | |
| M12 | `merge_cdn_headers` per key | |
| M13 | Modal push/pop no-ops | |
| S6 | `toggle_favorite` argument order | **fixes a 2.2.0 bug** |
| AC1 | Fetch-before-save on a playlist add | keeps the good half of `bc163e0` |
| CC1/CC2/CC3 | msgpack caching and the sidecar | measurable cold-start win |
| AP1-AP8 | The anyio pools and the liveliness semantics | **the "offline is unknown, not dead" fix is a genuine quality improvement** |
| HX2-HX9 | The HLS proxy hardening, minus HX1 | |
| LS2/LS3/LS5 | The scanner consent flow, path resolution and dedupe | |
| T1-T5 | Thumbnail cache keying, bounds and atomic writes | |
| PM1-PM3 | Permissions | |
| U1-U4 | The utils fixes | **and give the favourite toggle a test** |
| DB1-DB9 | The database hardening | **and test the backup-recovery path** |
| K5-K9 | The deep-link gates | |
| K14 | The order-sensitive `channels_hash` | **fixes a real 2.2.0 bug** |
| K18-K22 | The theme and token rework | decide K19 separately |
| SC1-SC22 | The screen fixes, notably SC3 (the false "could not reach the license service") and SC17 (credentials on screen) | |
| CI1/CI2 | Pre-release publishing and the version defaults | |
| CI6/CI7 | The `jni` override and `media_kit_libs_windows_video` | **build-breaking if omitted** |
| DP1-DP4 | The dependency and tooling changes | |

### Tier 4: The notification feature set. Decide it as one unit, not as eleven changes.

| ID | Change | Note |
|---|---|---|
| N1-N11 | The whole notification layer, the manifest patch and the tap handling | **All of it is dead on Android 13+ without CI3. Either take the patch or drop the notifications; taking the code without the patch is the worst option.** |

### Tier 5: Do not re-apply without a separate decision and a separate test.

| ID | Change | Why |
|---|---|---|
| L1-L3 | The watcher abort and backoff | a real design change to the path you said works perfectly |
| L4 | The "Premium ended" notification | it announces a pre-existing glitch loudly |
| K23 | Credentials refused in stream URLs | may break real playlist entries |
| HX1 | TLS verification on for every host | needs a real playlist to validate |
| LS4 | The narrowed scan paths | narrows what the app can find |

---

## Part 5: Test coverage gaps

These are behaviours that are correct on HEAD, or that were deliberately chosen, and that **no test pins**. Any of them can be silently reintroduced by the next refactor. This is the list to close first.

| # | Behaviour | Where it should be pinned | Risk |
|---|---|---|---|
| 1 | The Home grid is a plain expanding scrolling `Column`, with no `AnimatedSwitcher` and no per-page `key` | `tests/test_channel_grid.py` (currently one assertion that the function is a component) | **The exact bug the user reported. The revert is entirely unpinned.** |
| 2 | The Quality and Audio chips stay invisible until the probe finds real options | `tests/test_player_handlers.py` - the class shell at line 344 survives but contains **no test methods** | The two tests that pinned it were deleted by `fb625bb` |
| 3 | The `file://C|/Windows/...` pipe-separator bypass is rejected | a new test in `tests/test_url_validator.py` | The only security fix in the release with no automated pin |
| 4 | `toggle_favorite` / `toggle_favorite_async` | a new test in `tests/test_utils.py` | The only in-scope change with no test at all |
| 5 | The database backup-recovery path: the backup is restored and a quarantine file is created | `tests/test_database_manager.py` | 2.2.0 lost the whole app on a corrupt store; the fix is unpinned |
| 6 | `_validate_loaded` migration | `tests/test_database_manager.py` | One corrupt row used to crash every reader |
| 7 | The onboarding selection clamp | `tests/test_settings_screen.py` | a stale country can be submitted |
| 8 | The theme-save cancel and the toast-hide cancel | new tests | two "final state wins" bugs with the same root cause |
| 9 | The `AnimationSwitcher`-free grid on the Local screen and the search pager | `tests/test_channel_grid.py` | |
| 10 | The boot path: `import src.main` in a fresh interpreter | a CI smoke step | **The suite was green while the app raised `ImportError` on every boot.** |

**The tenth one is the most important.** Every other entry on this list is a specific behaviour. That one is a class of failure. A unit test suite that passes does not prove the application starts. The next release needs a boot smoke test.

---

## Part 6: Documentation at HEAD that is now wrong

| File and line | What it says | Reality |
|---|---|---|
| `src/core/constants.py:215-217` | "the service builds an explicit 4-tuple from it so pool acquisition stays tight" | it passes a bare scalar 15.0. The 4-tuple implementation was in the reverted `kiri_license.py`. |
| `src/core/logger_handler.py:1-8` | "`setup_logging` must also lower the root level (it sets DEBUG)" | `setup_logging` now sets INFO. |
| `docs/manual-test-plan-2.3.0.md`, closing section | "The `flet-notifications` analysis is research only - nothing is wired in" | `flet-notifications` is a runtime dependency and the CI patch step is wired in. The plan also predates the entire notification work and contains no test steps for it. |
| `docs/release-notes-2.3.0.md` | "803 tests" | the collected count at HEAD is 777. The changelog entry in `src/core/changelog.py` says 783. The last commit claims 810. |
| `docs/release-notes-2.3.0.md` | "Independently audited across every source file, then every finding fixed and re-audited" | accurate as written, but it carries **no device-verification record**. |
| `docs/2-3-0-decision-list.md` (untracked) | describes a proposed restore of six files | it does not describe HEAD and must not be used as a description of the shipped tree. |

---

## Part 7: What this cycle actually taught, for the next one

1. **One giant commit is the root cause of the whole mess.** `937c211` changed everything in one commit. Every regression the user found traces to it, and every fix became a separate corrective commit. The next 2.3.0 should be six or eight small, independently revertible commits, each with its own test.

2. **Reading code is not verifying a fix.** The first audit wave reported no blockers from code reading. The white player produced a healthy stream and a broken picture. The rule that held up: **diff the serialized control tree, or look at the screen.**

3. **A green suite is not a bootable app.** `943f671` imported a module it did not commit. 803 tests passed locally, CI failed, and the app would have crashed on launch. Add a boot smoke step.

4. **A revert must be re-verified against everything else.** `2bee4e1` correctly restored licensing and silently wiped the close-path fix and the reconnect gate. Every revert needs a diff against the *whole* tree, not just its target files.

5. **Never delete a test in the same commit as a revert.** `fb625bb` reverted the grid and removed 847 lines of tests across ten files, describing only the grid. Three behaviours are now unpinned.

6. **A feature that needs a build-system step is not a feature until the build step is verified.** The notifications were complete and correct in Python, and dead on Android 13+ because the manifest patch was missing. The patch step itself is still unverified, and it is the single highest-risk item in the release.

7. **Ask before changing the licensing.** It was working on the user's phone. It was changed, it broke, it was reverted, and the revert left three changes on top of the v2.2.0 base that were never individually examined. The correct default for licensing is: **do not touch it unless the user asks.**

---

*Compiled 19 October 2026 from three independent read-only investigations over `v2.2.0..HEAD`. Every claim cites `file:line` at the head commit. No code was changed while producing this document.*
