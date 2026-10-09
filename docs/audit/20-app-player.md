# 20 — App Audit: Entry + Player (main, app_shell, player/*)

Files: src/main.py (1005), src/app_shell.py (185),
src/components/player/immersive_player.py (1204),
src/components/player/controls.py (325), src/components/player/handlers.py (531).
All Flet APIs verified against installed 1.0.1. No hallucinations found.

## main.py — Bugs Found (not production-ready)

High:
- H1 lifecycle hidden checkpoint dead (:166-174): checks `e.data == "hidden"` but
  event carries only `e.state: AppLifecycleState`. _save_top_player_position
  unreachable. Fix: save on HIDE/PAUSE/DETACH, reconcile on RESUME/SHOW.
- H2 fallback deep link omits /blank underlay (:738-753 vs :770-781): single-view
  stack → system back exits without save. Mirror ktv:// branch (append /blank).
- H3 play_stream dup suppression doesn't suppress (:512-519): lock created lazily
  (two entrants make two locks); locked()-then-acquire only serializes, second
  still plays + pushes second /play. Use init-time locks + playing flag/debounce.
Medium: push/close/pop_modal async with sync bodies (:315-335) → plain def;
_close_player plain-pop skips teardown+save (:642-668) → funnel all closes through
_close_player_with_save; close-save double-schedule race (no check-and-set lock);
monkey-patched Page attrs + undeclared update_service/_controller_methods → declare
+ typed accessors; imperative views mutation fights declarative render (:214,
:437-457, :624-637); first-frame blocking HLSProxy.start + init_db before render
(:73-74, :100) → post-render or wait_for w/ degraded fallback.
Low: _on_global_error over-suppression while /play exists; play_stream re-raise
double-notify; CDN header replace-not-merge; missing return annotations + lazy
imports; page.update on tracker-only modal changes.

## app_shell.py — Bugs Found

High:
- H1 swapped toggle_favorite args (:164-165): calls (state, url), signature is
  (url, state) — Search favorites silently dropped (AttributeError swallowed).
  Fix: toggle_favorite(url, state).
- H2 asyncio.create_task for playback (:159-162): RuntimeError with no loop +
  unretrieved exceptions. Fix: context.page.run_task(controller.play_stream,...).
Medium: context.page guard assumes None-return but property raises RuntimeError
(:91-96) → try/except (use_keyboard_shortcuts already does); render-phase controller
mutation (:65,77,81) — stale back-press window; imperative view.navigation_bar +
page.update in use_effect with swallowed errors (:93-128) — stale bar/drop risk;
_shell_view route allowlist fragile (:48-51) — tag shell view explicitly;
_on_tab_change no bounds guard (:109-114).
Low: fresh closures per render defeat memo; function-level imports per render;
per-render tuple(state.favorites) O(n); zip strict needs 3.10+; no NavigationRail
variant (enhancement).
Checked OK: hook order, use_memo short-circuit, onboarding-complete no-op wiring,
Icons/NavigationBar/ValueKey/SafeArea shapes, D-Pad delegation to FocusScope/player.

## immersive_player.py — Bugs Found (close, not ship-ready)

High:
- H1 PiP never arms on slow networks (:631-640): is_playing checked once right
  after play; slow start False → never re-armed. Also arm on first position tick /
  on_load.
- H2 periodic position checkpoint dead (:693-722 defined, zero callers):
  _on_pos_change never calls _maybe_save_position_periodically. Call it.
- H3 background-pause fights PiP (:315-316 + :409-441): pause+resume True freezes
  PiP frame + resumes user-paused video. pause=False while PiP armed/available,
  resume=False + explicit user-pause tracking.
Medium: M1 _swap_media never resets _is_final_error (:883-930) → watchdog exits +
  errors suppressed after swap; reset in _show_progress/swap head. M2 close can
  hang forever (:1188, :1129-1137): wrap stop/getters in wait_for 1-2s. M3
  _on_complete fire-and-forget DB write + possibly un-awaited handle_stream_complete
  (:1159-1172): verify sync/async, use page.run_task if coro, track task. M4
  will_unmount duplicate/unguarded save (:376-396): check _position_saved, guard
  get_running_loop RuntimeError, drain _orphan_tasks at exit. M5 _manual_retry arms
  PiP unconditionally (:1119): gate like start_playback. M6 on_load never subscribed
  (:355-361): subscribe for ready signal (hide/arm/probe). M7 volume unvalidated
  (:146,:311 vs video.py:222-227): clamp 0-100.
Low: L1 ms/us heuristic misclassifies long VODs; L2 overlay hides on 0/invalid tick;
L3 deferred seek optimistic + truncates; L4 click lambdas use page not safe_page;
L5 silent except; L6 lifecycle-restore stores handler not page; L7 no auto-retry +
dead _retry/_reconnect/_was_closed_during_ad counters; L8 filter LOW vs MEDIUM
guidance; L9 snapshot shows content:// URI + failure only logs + JNI thread risk;
L10 `if pos` truthiness → is not None; L11 per-stream title renames OS mixer entry.
API check: play/pause/stop/seek/is_playing/duration/position/screenshot,
playlist NONE + update-before-play, custom Control, all bound events, Duration
payloads — all correct. on_load available-unused; on_track_change correctly unused
(NONE + 1 item); pitch correctly unset; volume enforced at before_update.
Concurrency: 6 orphan tasks (arm/disarm ordering racy — generation counter);
will_unmount + periodic orphans undrained; swap wait_for inner-future linger;
is_playing-after-play race; close-vs-unmount playlist race (benign via guard);
lifecycle last-mounter-wins onto possibly stale loop.

## controls.py — Conditionally ready (fix H1/H2)

High:
- H1 toggle_favorite may never execute (:177): bare sync call; if callee async →
  unawaited coroutine + silent DB loss. Verify signature; use page.run_task if coro.
- H2 triple-update partly invalid (:179-192): fav_btn/speed_container/quality_btn
  live INSIDE video.controls (serialized as native value, not mounted) so child
  .update() throws/no-ops (masked by bare except); video.update pushes subtree;
  page.update redundant. video.update() only.
Medium: M1 same instances shared across material + material_desktop (:243-323) —
  single-parent risk; factory fresh instances per branch. M2 quality/audio chips
  content=None padding=0 (:89-96,:118-125) — zero-size until probe sets content;
  give min size (width/opacity) so layout doesn't shift. M3 favorite snapshot goes
  stale on resource change (:131-150,:152-194) — recompute on media load/on_load.
Low: tab_index on Container dubious; shared btn_style mutation risk; Margin order
verify; chips should route to open_quality_picker not full settings.
API: all Adaptive/Material/Desktop kwargs, Spacer, PlayOrPause, Fullscreen,
PositionIndicator, VolumeButton(desktop) — verified correct.

## handlers.py — Ready with minor fixes

High: none. Medium: M1 audio probe gated behind variants (:166,:370 ternary
precedence — single-variant multi-audio never shows; fetch tracks unconditionally).
M2 Dropdown.on_select needs verification vs on_change for pinned Flet (:335,:361).
M3 redundant updates (cycle_speed video+speed_text; _refresh 4x sibling updates →
single dialog.update). M4 appended FilePicker never pushed (no page.update after
services.append :72-74). M5 local subtitles broken on web (path-only guard :82-90;
handle bytes/disabled on web).
Low: _close_dialog/dialog defined-after-use (works, fragile); "1.0x" formatting;
dialog height mistally; stale variant/audio Dropdown coercion; reconnect drops
rate/subtitle/pinned variant + non-HTTP silent black screen; page.close(dialog)
idiom + double-open guard.
Correctness: speed (playback_rate+update, live guard), fit (BoxFit+update),
subtitle (auto/none/src+title, assignment+update), track wiring
(list/apply + checkmarks) — all correct API use.

## Cross-file triple-update inventory

controls.py:179-192 → video.update() only. handlers.py:29-31 → video.update() only.
handlers.py:401-405 → single dialog.update().
