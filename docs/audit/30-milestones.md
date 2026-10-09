# 30 — Milestones to Production Standard

Rule: plan mode → plan ONE phase → approve → implement → back to plan mode →
plan next. No phase touches ads/consent code or version.json without explicit go.

## Phase 1 — Data loss + crash paths (ship-blockers, no UI redesign)

Scope: provider tier tag + lock-await + stale fallback; app_loader copy-on-merge +
empty guard + row validation + cancellation; database backup-on-corruption + empty
handling + entry validation + dirty-flag bool; history legacy parsing + empty-URL
filter + credential masking; favorites loop/concurrency guards; core state
dataclass/hash/reset/notify fixes; controller_ctx slot signatures + no-mutate.

Docs: 31 (provider/app_loader/database/history/favorites/state/controller blocks),
25 (normalize H1, manager, favorites, state, controller), 23 (app_loader, state),
21 (recently_watched screen), 22 (recently_watched component), 17 (pytest mock fix
for the RuntimeWarning + strict config can ride along, test-only).

Exit: offline refresh keeps stale grid; tier flip serves right list; corrupt/legacy
DB never crashes + backup tried; history screen never crashes on legacy data;
no silent favorite drops; state hash order-sensitive; controller defaults never
TypeError. Tests: full suite green, warning gone.

## Phase 2 — Player reliability

Scope: on_load ready signal + PiP arm on ready/tick; periodic save wiring;
bg pause/resume vs PiP coordination; _is_final_error reset on swap; close
timeouts (stop/getters wait_for); unmount save guard + orphan drain; volume clamp;
MEDIUM filter quality; controls single-update + shared-instance split + favorite
await check; handlers audio-gating + on_select verify + FilePicker update + web
subtitle path; video_card thumbnail reactivity + nested-clickable restructure;
pitch knob assessment (KTV key-shift — product decision first).

Docs: 11 (video API reference), 20 (all player findings), 22 (video_card),
31 (player blockers).

Exit: slow-network PiP arms; position survives kill + close; no stuck Back button;
no reconnect-over-error; quality/audio swaps dismiss spinners; thumbs update
without rescan. Tests: player handler + PiP + close-path tests.

## Phase 3 — Navigation + back stack

Scope: lifecycle e.state save/reconcile; fallback /blank underlay; play dedupe flag;
close funnel (all closes through save path); router push for history (guard dup);
View appbar slot + explicit back leading; AppShell favorite arg order + run_task
play; focus autofocus + guarded page + tab bounds; keyboard/shortcut identity
guards + Cmd modifier + stale closure fix; focus_scope autofocus + key-set verify.

Docs: 20 (main/app_shell), 21 (home/recently_watched screens), 25 (focus hooks,
controller_ctx), 10 (lifecycle/routing APIs).

Exit: minimize saves position; no single-view strand; no double player push;
Search favorites persist; Back/Esc reliable incl. TV; shortcuts survive
mount/unmount order. Tests: back-stack + lifecycle + shortcut tests.

## Phase 4 — Network hardening

Scope: shared client http2 + UA + hooks + retries + explicit 4-part timeouts;
playlist stream+cap + error identity (raise vs []); HLS verify-on + per-host
exemptions + 502+ reason table + 400s on bad input + SESSION-KEY rewrite +
Content-Type routing + read timeout/caps; liveliness tri-state + streaming probe
+ shared semaphore + no PoolTimeout caching + GET-fallback narrowing; logo queue
dedup + eviction on worker path + loop ownership + negative-cache respect;
update announcement branch + mandatory parse + return-type + timeout; deeplink
gates/caps/validation + validator hostname/control-char/Windows-slash/encoding
fixes.

Docs: 14 (network reference), 24 (http/hls/iptv/liveliness/logo/update/deeplink),
23 (deeplink, url_validator), 31 (network blockers).

Exit: no MITM-able global no-verify; no player hangs on bad input; no OOM on
hostile playlists; dots never red from pool exhaustion or offline; logos bounded.
Tests: proxy + validator + liveliness + logo tests.

## Phase 5 — Licensing durability

Scope: DB clear on every revoke/reject/non-active; apply_cached_token honest clear;
typed LicenseUnavailable (status_code/is_refusal) + abort-vs-retry in watcher;
input coercion + dict/float guards; 400-out-of-refusal set; restore/refresh retry
or consecutive-failure gate; reconcile/watcher supervision + forced hourly +
timestamp-after; token verify-before-parse + size caps + paid_through/v/iat/now/SPKI
strictness + fixed inactive reason.

Docs: 24 (kiri_license, license_token, premium_service), 31 (licensing blockers).

Exit: revoked stays revoked across reboot; hard-400s abort watcher, transients
retry; no UI crashes on malformed payloads; renewal re-arms. Tests: license +
premium + token tests. NO Play-build behavior changes; Play channel stays free-only.

## Phase 6 — Device paths (needs on-device verify)

Scope: MediaStore ID-based discovery + Java String[] projection + drop exists gate
+ duration/mime/modified columns; SAF primary + graceful-unknown + normpath;
scan targeted dirs + set-dedup + normalize keys; permission get_status/LIMITED/
permanent→settings/SDK-branch/wired-bool/boot-registration; local_screen
generation counter + background-no-wipe + task cleanup + service singletons +
consent progress UX + banner keys; thumbnails model guards + frame fallback +
os.replace + tmp cleanup + return semantics + dedup + absolute dir + purge;
PiP real return + activity revalidation + MainActivity verify + UI-thread calls;
sfx singleton + guarded release + MUSIC/60/0.3s; tv_detect per-attr probe +
in-function candidates + retry cap; device_info $VERSION + per-field + no-traceback.

Docs: 16 (Android reference), 24 (scanner/permission/tv/device/thumbnails/pip),
21 (local_screen), 22 (folder_tile/video_card), 13 (permissions).

Exit: Android 10+ discovery returns videos; SD cards degrade gracefully; permission
denial explains + recovers; no scan stampede; thumbs bounded; PiP verified on
hardware. Tests: mocks (native parts need hardware confirmation by you).

## Phase 7 — UI correctness + accessibility (TV-first)

Scope: grid subscription + ad-branch decision + banner memo + page clamp/scroll-top
+ button pagination + seeding identity; filter pill predicate + focusable Fav/+
+ focus follow + labels/checked/hit-targets; cards star restructure + logo-src
verify per target + None/empty guards + tooltips/semantics + placeholder/gapless;
header page-guard + reactive update chip + asset path + overflow; loading responsive
+ label contrast; onboarding persist guards + double-submit + flash + fallback;
settings task ownership + error toasts + dialog bounds + retry; version_dialog
OpenUrl-in-gesture + instance tracking + progress + mandatory guard; empty_state
width + button contract; theme brightness/on_secondary/unified dark + density call;
tokens namespace/units/fonts; changelog fallback + helpers; crash reporter
filenames/timezone/cleanup/traceback; logging install/level/dupe/format;
init facades (relative + complete) + channels/__init__.py.

Docs: 22, 23, 21, 10, 31 (all UI leftovers).

Exit: pages 2+ dots live; D-pad reaches every control with visible focus; no
overflow on small screens; dialogs never stack/dup; update chip live; first launch
never half-writes. Tests: component + screen tests.

## Phase 8 — Performance + architecture paydown

Scope: anyio adoption per subsystem (task groups, scopes, streams, limiters —
no anyio.run in loop); msgpack liveliness cache + channel sidecar (JSON fallback,
on-device ext verify, promoted dep); memoize cards/callbacks/banners; playlist
parse off-loop + parse-once + concurrent tier fetch; image flags everywhere;
AnimatedSwitcher swaps; Dismissible/Reorderable/ExpansionTile/Hero/Share/Haptic
assessed per screen; ruff rule expansion + fix hits; pytest strict config +
anyio unification + xdist + sleep removal + parametrize; dead code + docstring
accuracy pass.

Docs: 10, 11, 14, 15, 17, 31 (all improvement items).

Exit: cold start faster (sidecar + decode); no orphan tasks (groups + joined
shutdown); lists don't rebuild per tick; lint catches dangling tasks/blocking IO;
suite parallel + warning-free. Benchmarks recorded in docs.

## Ads (separate, needs go each time)

Doc 12 only. Telemetry/lifecycle/gating observations queued. No edits until you
approve each item explicitly. TV stays ad-free (IMA/disabled route); mobile only.
