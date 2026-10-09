# 21 — App Audit: Screens (home, local, search, settings, onboarding, recently_watched)

## home_screen.py (404) — Bugs Found

High:
- H1 navigation stack leak (:298-316): views.append(/recently-watched) per tap,
  no guard/pop wiring, fights router. Route via router or guard existing top view.
- H2 global liveliness callback never unregistered (:198): set_on_change singleton
  overwrite, no cleanup → dead closure forces renders after unmount. cleanup →
  set_on_change(None) (or multi-listener support).
- H3 banner rebuilt every render incl. 500ms ticks (:322-331): new AdService +
  BannerAd per render → request storm/flicker. use_memo on stable deps.
Medium: M1 stale-closure filter overwrite (_commit_search deps only debounced_search
but replaces full filters; on_filters_updated merges stale) → functional set_filters
updates. M2 double drain/seed race with channel_grid (both drain_queue+enqueue;
different slices/deps; typing churn) → single seeding owner. M3 dead search wiring
(search_input/debounce/commit exist but Header/FilterBar receive nothing) → wire
or delete (+ commit wipes country/category/custom/fav). M4 fire-and-forget tasks
(:62,:191,:221,:266) → page.run_task + cancel + play debounce. M5 dialog in layout
flow (:373-377) → overlay/page.dialog. M6 seed watches filters not filters_eff
(:169) → depend on filters_eff/visible.
Low: render logger.info per tick → debug; reset_notified never reset; tuple(favs)
per render; use_ref vs ft.* inconsistency; salted channels_hash collisions;
function-level imports per effect.
Checked OK: FloatingActionButton bottom/right in Stack valid (LayoutControl);
lazy use_state init; updater-form version bump; hook order before early returns.

## local_screen.py (470) — Bugs Found

High:
- H1 background rescan wipes grid (:163-166,:387): except → set_folders([]) on
  background delete-verify path. Never clear on background failure; log + keep.
- H2 scan serialization comment wrong; overlapping scans queue (:15,:145,:181-185,
  :226,:259,:387): lock serializes, not last-wins. 5 taps = 5 full to_thread scans.
  Generation counter (latest applies) or debounce.
- H3 _prewarm_task cancelled without retrieve, no unmount cleanup (:18,:158-179):
  "Task exception never retrieved"; no on_unmounted cancel for scan/prewarm/
  consent polls → set_state on dead page.
Medium: M1 permission bool ignored (both entries) → skip scan + explainer + settings
action. M2 service-per-call leak (StoragePaths/SharedPreferences per scan/prefs;
auto-register + page update per construction, never unregistered) → per-mount reuse
or page-identity singleton. M3 FilePicker via getattr page.file_picker (not Flet
API; monkey-patch) + duplicate leak → register once at shell startup. M4
context.page re-read inside slow tasks → capture once per mount, thread explicitly.
M5 fire-and-forget, no error surface (:185,:188,:229,:290,:409-411) → _safe_task
wrapper logging task.exception. M6 delete consent blocks ≤20s, no UI (:326-395) →
progress + 0.5s poll + early decline exit. M7 banners/tiles rebuilt per render,
no keys (:397-433) → memoize banners, key footer, confirm tile key forwarding.
Low: prefs JSON unvalidated; web picker exception → generic message; empty resolved
path guard; FAB lambda per build (pass directly); f loop var; module-global lock/
task break multi-instance; from flet import Control style; _async_remove wrapper.
Permission/scanner/picker/prefs: permission_service logic correct, result unused;
storage-paths merge sound, missing existence filter/timeout/generation; picker
signature correct (CancelledError early-return OK), singleton lookup risky +
concurrent double-picker; prefs type-correct, validation-poor + per-call construct.

## search_screen.py (420) — Bugs Found

High:
- H1 single-slot liveliness listener clobber, no cleanup (:39-62): mounting Search
  overwrites Home listener; unmount never restores → Home dots freeze. Multi-listener
  or cleanup→None. _flush task can set_state after unmount.
- H2 unguarded ft.context.page (:404): raises RuntimeError off-session; try/except →
  None (build_banner_ad tolerates None, not the raise).
- H3 fire-and-forget local auto-scan, no loop guard/cancel/UI state (:64-80):
  create_task in sync effect, no RuntimeError guard, set_state after to_thread with
  no unmount check, bare except pass. Loop guard + mounted flag + loading/error/retry.
- H4 local path passed to stream handler (:277-279 + app_shell): on_play(path) into
  play_stream(url,None) — confirm play_stream branches local vs URL or local results
  silently fail. Both create_tasks lack done-callbacks.
Medium: M1 controlled-value + stale search-button closure (:149-170 cursor/focus risk;
button reads render-closure field, one render stale; submit waits full debounce) →
source-of-truth query + immediate flush/ref. M2 deprecated TextField border API
(:155-157; delete 1.3.0) → border=OutlineInputBorder. M3 initial_mode never resyncs
+ stale snapshots (:24-31; no key= from app_shell; set() new identity per render
defeats memo; fav toggles need parent rebuild). M4 local filter matches absolute
path + nullable fields unguarded (:237-243; "c" matches C:\...; None.lower throws) →
basename/stem + or "". M5 nested scrollables + duplicated PAGE_SIZE (:254-400;
Column AUTO > ListView expand; hardcoded 24 vs constants) → single scrollable,
shared constant, keyed tiles. M6 per-render imports (:44-45,:52,:60,:68,:402) → top.
Low: from flet import Control style; _liveliness_version unread; effect returns
setter; with_opacity correct; icons verified; disabled containers still clickable
(set disabled+opacity); content_padding int → Padding.all; raw query in empty-state;
page-label double space + shared footer; mode toggle not keyboard/semantics selectable.
Wiring: mode toggle correct; debounce correct (no flush on submit = M1); liveliness
coalescing correct, subscription broken; TV path correct, local suspect (H4).

## settings_screen.py (1023) — Bugs Found

High:
1. asyncio.create_task for Flet work ×8 (:265,:269,:274,:279,:310,:449,:627,:640):
   loses page context + swallows exceptions. → page.run_task everywhere.
2. Country save fire-and-forget, no error path (:443-449): _do no try/except;
   exception never retrieved; UI shows unpersisted country. try + notify_warning.
3. URL launcher no failure feedback (:670-674,:676-683,:851): bare launch_url;
   mailto/bad URLs raise into loop handler, user sees nothing. try + notify_warning.
4. premium_service.license deref without guard (:979-982): service exists but
   .license None → AttributeError. Nested getattr.
Medium: 5. service-per-click leak (:228,:672,:851,:910 Clipboard/UrlLauncher
auto-register per construction) → hoisted shared accessor. 6. premium listener
cleanup fragile (:785-799 setup-return-as-cleanup; scheduler-dependent) → explicit
cleanup=_cleanup / on_unmounted. 7. country picker overflow (:535-570; 177 rows,
no height bound in AlertDialog.content) → fixed-height Container + search field.
8. _load_license silent when unavailable (:807-811; products=[] forever, no retry) →
explicit retry button. 9. log dialog lifecycle (:258; 0.5s scroll on detached col) →
cancel on dismiss. 10. Switch autofocus steals focus every visit (:509; TV D-pad) →
False.
Low: dead _SECTIONS; unread _theme_mode; page.update for dialog-local mutation;
Image color tint monochrome question; tuple-return on_click; _premium_subtitle
AttributeError gap; banners always Container (layout spacers).
Flows: theme toggle+ persist + rebuild sound; country write+toast OK except #2;
history/library clear correct; premium CHANNEL gating correct, gaps #6/#8 + no
checkout_url validation; update check separation correct (noop-controller → silent
tap, add guard toast); rate/more-apps routing correct (_is_store_device), mailto
needs #3.

## onboarding_screen.py (283) — Needs Fixes

High:
- H1 unhandled persistence failure bricks first launch (:34-47,:50-56,:110-122):
  storage.set_setting no try/except; exception out of click handler; half-written
  (country without terms); no feedback on blocking screen. try/except + error toast.
- H2 no submit/skip guard, double-tap race (:106-122,:244-251): no is_loading/
  disable while persisting; duplicate set_setting + duplicate on_complete (no-op
  today in AppShell, double-nav when wired).
- H3 first-frame form flash (:76,:90-98,:124-130): is_loading starts False →
  form → spinner → form/offline. Init from prober is not None.
Medium: M1 country fallback dead (:101-104): extract_country_dicts always appends
Other → `or countries` never fires; static prop ignored when channels empty.
Intended: channels ? extract : countries. M2 nested same-axis ListView
(:163-169 in :174-256; inner height-180 scroll traps gestures) → fixed column or
explicit physics. M3 submit validation unreachable (:114-119 vs :249; disabled
button never fires → warnings defense-only; users get no why-disabled). M4 probe
swallows all silently (:81-88) → log debug/exception.
Low: width=float inf → expand; Checkbox autofocus weak for TV (use focus hooks);
_notify_warning alias + _maybe_invoke unguarded sync raise; build_controls_on_demand
unnecessary; deferred OfflineFlow import → top.
Verified OK: all Flet APIs exist w/ compatible signatures; persistence keys/flow
match main boot read; Image /icon.svg matches assets_dir + file; focus valid but
weak; navigation state-driven (observables), on_complete awaited both sync/async.

## recently_watched_screen.py (133) — Needs Fixes

High:
- H1 AppBar in Column, no back affordance (:118-132 + home:304-316): View.appbar
  slot unused; pushed View has no appbar= → no visible back (system-back only).
  Set appbar= on View in caller + explicit leading pop.
- H2 legacy string crashes whole list (:26 vs :36-40): entry.get before isinstance
  → AttributeError; else-branch dead. isinstance-first + skip empty URLs.
- H3 on_play arity untyped/fragile (:21,:85 calls 2-arg; home handler takes 2, but
  siblings declare 1-arg) → type Callable[[str,str|None],None]; standardize all to
  (url, title=None).
Medium: M1 delete flow ABSENT (no remove/clear-all/confirm despite LBL/SM/settings
support) → per-card delete + clear-all AppBar action. M2 stale snapshot (history
passed once; add_to_history rebinds → open view stale) → rebuild on show / reactive
read. M3 raw URL subtitle incl. credentials (:69 url[:60]; user:pass@host leaks on
screen/share) → domain-only/masked/title-only. M4 remote logos, cache never warms
(:42-46; no enqueue) → shared helper with screen + component. M5 _display_name junk
for extension-less URLs (:11-15; numeric IDs, %20 raw, trailing / → Stream) →
unquote/strip query/domain fallback.
Low: per-card sync IO (8 syscalls × 20 items) → memoize/async; no virtualization
(add build_controls_on_demand + cache_extent); unguarded context.page (:115);
empty-URL entries render + play ""; function-level imports → top; history list[dict]
vs legacy strings; no tooltip/semantics; empty state no CTA; zero-size banner
placeholder.
Flet APIs all valid (Container ink/click, Image src/fit/radius/error_content,
ListView controls/expand/spacing/padding, AppBar title/center_title, HISTORY/TV
icons, grey_dim fallback, bounded ListView-in-Column layout). No concurrency
issues (no async/threads; rebound-not-mutated iteration).
