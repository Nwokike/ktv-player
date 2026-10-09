# 25 — App Audit: Channels / State / Hooks / Utils / Database / Inits

## channels/normalize.py (101) — Needs Fixes. No crashers; keys line up w/ parser.

Parser contract good (m3u_parser keys match; .get+defaults None-safe). Wiring good
(provider tier→premium/legacy; _compose keeps legacy YouTube + premium; re-parse
from disk → no double-mutation). Downstream consistent (country/categories direct;
get_countries excludes Global+custom, sorted). tvg-id shapes handled (@-strip,
dot-split, trailing/empty→None).
High: H1 fallback shadowing (:90-93): any 2-3 letter tvg-id suffix truthy
("hd" from News.HD) suppresses valid tvg_country (us → Global not US). Validate
against country_name() before accepting, then fall through. Keep real code (fixes
M3 too: :82,:98 country_code="M3U" discards ISO; search "m3u" matches all geo).
Medium: M1 NON_COUNTRY_GROUPS incomplete + default fragility (:29-44,:77-79;
missing custom/undefined/entertainment/series/animation/singulars; group="Custom"
parser default → country="Custom" bogus — masked only because provider:97
overrides General; direct parse+legacy or Entertainment → country-folder bug).
M2 legacy case fragmentation (:79-80,:94 premium canonical Title vs legacy raw →
"Nigeria"/"nigeria" distinct in get_countries) → strip+title/canonical map.
M4 _is_category_word perf+correctness (:63-67 ~14 regexes/channel → 140k compiles/
10k chans; misses singulars) → precompiled single (?i) or tokenize+set.
M5 unconditional is_custom=False (:83,:99; re-normalize merged list de-customs;
header claims legacy covers user playlists; app_loader marks after merge) →
setdefault/flag. M6 single-country → categories=[] (:81; vanishes under category
filter; legacy fallback ["General"]?; decide empty vs General).
Low: L1 [a-z]{2,3}$ accepts hd/sd/en (membership check). L2 multi tvg-country
unsplit ("us;uk"/"US,GB" → Global; split [;,|/\s]+ first-known). L3 in-place
mutation same-list return (shallow-shared surprise; idempotency guard). L4
case-sensitive dedup ("News;news" kept; casefold key). L5 reverse groups lose
country ("News;Nigeria" → Global + "Nigeria" category; only parts[0] tested —
documented; scan-first-non-category improvement).
Fix: H1 validate-then-fallthrough + real code; M1 sentinels (custom/general/
undefined/other + singulars) or explicit custom/general guard; M2 canonical +
categories-or-General decision; M4 precompile/tokenize; M5 setdefault; L2 split
each-against-country_name; L4 casefold dedup.

## database/manager.py (287) — Bugs Found.

High: corrupted recovery never tries .bak (:59 elif only-if-missing; exists+bad
JSON → rename .corrupted + return {} ignoring valid backup → data loss; fall
through to bak). empty file clean-empty (:53-54,:61-63 0-byte → {} w/o bak/
quarantine; +no fsync → crash-during-replace permanent loss). no load validation/
migration but runtime assumes dict (:69-72 verbatim copy; :103/:111/:131/:143/
:187/:201/:222/:258 .get/["url"] crash on str/int/None; get_history migrates
str proving legacy exists). failed save marked clean (:94-95 _write swallows
:91-92 then _dirty=False unconditionally → close :282-283 believes safe).
Medium: db_path ctor arg dead (:26,:29-34 never uses db_path; custom path silently
default). dumps outside try (:76-78 non-serializable → propagates out of lock;
callers unhandled; move inside guard). async getter leaks alias (:140-145
returns internal e; sync dict(e) correct; same :159,:194,:208,:237 → copies).
set_setting str-coerce (:171-174 destroys bool/int/float; get(x,False)→"False"
truthy → store natively + delete_setting). remap duplicates (:239-254 new_url
exists → two entries; drop/merge). liveliness cast unguarded (:265-272 float(val[1])
raises under lock aborting load → per-entry try). locking incomplete (:35,:147-155
asyncio across to_thread bottleneck; sync accessor lockless; loop-bound reuse
RuntimeError). corruption overwrites forensics (:56-58 fixed .corrupted name +
bare except, no ts/log).
Low: import-time I/O (:11-18,:286 mkdir + global manager → tests create dirs).
misleading "loaded successfully" (corrupt/empty fallback). [:50] magic + is_active
int + unconditional save when nothing removed + dict-cache ignored. with_suffix
tmp fragility (with_name clearer; no fsync/cleanup).
Persistence/locking/migration/history/fav: atomic tmp+replace + bak-optimization
correct pattern; broken by fsync/empty/dirty/dumps gaps. Locking: mutators/readers
take lock + _save_now no-reacquire (close safe) correct; getters alias + sync
bypass + loop-bound + across-offload incorrect. Migration effectively absent
(get_history str-coerce read-only, no int/None/missing-keys, no version/schema,
extra keys dropped). History dedup+carry+LIFO+truncate correct logic; broken by
validation/aliasing; no timestamp. Favorites add/remove/dedup + remap intent
correct; broken by dup + non-dict crash.
Fix: honor/remove db_path; load type-validate + migrate-once str→dict persist
dirty; recovery main-corrupt/missing/empty → bak + ts-corrupted + exception log;
_save_now→bool + dirty-on-success + dumps-inside + fsync + tmp cleanup; copies in
getters; native settings; remap dedup; per-entry cache guard; add
remove_playlist/channel or document; lazy ensure_dir; per-loop/thread-safe lock.

## hooks/apply_filters.py (123) — Needs Fixes. Happy path sound.

Medium: search None/non-string crash (:72 .strip on None). group None crash +
case-sensitive custom miss (:95 .split on None; `sports` vs `Sports` miss).
stale custom never reconciles when available_custom empty/None (:47-50 `if
available_custom and ...` conflates not-loaded None with loaded-empty {} →
saved DeletedPlaylist persists → zero rows). custom!=none drops country/category
(:86-115 custom-only, others ignored; UI resets so safe, contract undocumented →
document precedence or AND). category legacy hack breaks normalized (:113 second
clause group==category only for legacy "Nigeria;Sports" test; normalized
categories=[Sports,News] never matches full-group string).
Low: exact case-sensitive country/category (persisted-case zero-out → reconcile
masks cause). search name+url only (Sports/country/group → zero; "http" matches all;
spec-or-surprise). _default Other→Global (:54-60 extract always appends Other not
Global; no-Global channels → home sets Global → reconcile wipes to all; geo-default
defeated). None guards (favorites/channels/filters/c None throw; callers valid —
defensive). import + private naming (utils.channels src-on-path fragile;
_default_filters/_matches underscore yet imported by home + re-exported → rename
or __all__).
Logic: order search→fav→custom→builtin correct for mutually-exclusive UI;
custom all/single/group correct per tests + is_single_custom flag; defaults
none/all/all mixed-builtin+custom correct. Reconcile guards empty-as-not-loaded
correct for country/category + channels_loaded gate; custom gap only. Search
lower/strip/substring correct; `in` no regex risk; debounce upstream.
Fix: harden header (isinstance dict, filters-or-{}, favorites-or-set, str(search
or).strip); None-safe case-insensitive custom groups; None-vs-{} custom guard
(callers pass None pre-load); precedence docstring; normalized country/category
compare; optional search scope + min-len; tests for None/group/stale/contradictory.

## hooks/use_autofocus.py (45) — Bugs Found.

High: ft.MutableRef doesn't exist (:24 annotation evaluated at def, no future
import; grep __init__ zero hits, lazy map lacks it → import raises AttributeError;
latent only: zero call sites, not exported).
Medium: silent no-op for focus()-less controls (:39-43; only TextField/buttons/
Dropdown/SearchBar/KeyboardListener implement async focus(); Checkbox etc expose
autofocus prop but no focus() — docstring example suggests checkbox → silent).
bare except pass (:40-43 swallows must-be-added-first RuntimeError from
base_control:447-462; debug-log + page-None guard + one retry). docstring wrong
pattern+timing (:11-15,:30-32 manual .current assignment vs idiomatic ref= via
__post_init__; "reads each build" vs on_mounted once). dead code (repo grep:
file only; __init__ unexported → wire+fix or delete).
Low: stale 0.86.4/line-98 pins (installed 1.0.1); "via asyncio" inaccurate
(scheduler, not raw defer); None-check vs non-optional hint (MutableRef|None);
no enabled/re-focus path (document mount-only or add flag).
Not-bug: on_mounted async correct (Any|Awaitable); unconditional hook-scope
correct (callers keep unconditional). Timing adequate mount-case (scheduler drains
updates then effect; ref= + in-tree target works); late/conditional targets
silent no-ops. Cleanup none-required (no timers/subs; unmount clears; in-flight
await harmless).
Fix: import MutableRef from flet.components.hooks.use_ref (or future+TYPE_CHECKING)
+ import regression test; ref=-based docstring + mount-once semantics; native
autofocus prop guidance (already used search/settings/onboarding/empty_state);
warn-or-fallback (autofocus=True+update) for focus()-less; debug log + page guard;
enabled flag / refocus() return; export + caller or delete; drop version pins.

## hooks/use_debounce.py (41) — Needs Fixes. Core trailing-edge works.

High (API-contract risk): cleanup= kwarg (:39) — React-style but must verify vs
installed use_effect signature (return-cleanup vs kwarg); if unsupported → orphan
task set_debounced after unmount. (Split effect/cleanup closures fragile either way.)
Medium: deps omit delay_ms (:39; runtime 250→300 w/o value change never reschedules;
_after_delay closes stale). no CancelledError handling (:28-30 bare sleep+set;
cancellation correct-suppress today, explicit required for future code/warnings).
create_task no loop guard (:32 effect-context sync-run → RuntimeError; fallback
immediate). delay unvalidated (None/str/negative → task-internal ValueError/TypeError
never-retrieved).
Low: ref never cleared (cancelled/done Task held lifetime; None on cancel+success).
initial use_state(value) mount-only (documented-needed for controlled reset).
mutable value identity reschedules per render (document immutable-only). missing
types/validation/unmount doc.
Timer/cancel/cleanup: cancel-before-schedule correct value-change; cleanup logically
correct isolated (skip done, no await in sync); redundant double-cancel (cleanup +
schedule same ref); single-thread race-safe (no yield between wake+set except
done-case handled); unmount leak iff cleanup-API unsupported; no drift (fresh
sleep each change).
Fix: deps [value, delay_ms] + returned cleanup (verify signature first; one pattern);
captured=value default-arg; CancelledError→return; timer.current=None on
cancel+success; RuntimeError→immediate set; delay clamp (None/negative→0);
immutable-only doc.

## hooks/use_focus_scope.py (39) — Needs Fixes. Construction valid; delivery not.

High: H1 KeyboardListener never requests focus (:32-36; autofocus default False
:81, focus() :107-109 must own focus to fire on_key_down; in-repo settings:307-310
sets autofocus=True for same reason; sole call site main:627 player /play no other
request → hidden-overlay/no-button-focus Back/Escape dead). Fix: autofocus=True
(+expand directly on listener).
Medium: suspect "Go Back" (:10 set Back/Escape/BrowserBack/"Go Back"; space form
non-standard — GoBack/Back unverified; legacy focus_manager.py:31 cited file no
longer exists → log e.key on TV, prune/extend). unhandled on_back exception
(:26-30 result/await no try → player handle_close I/O raise → dispatch propagate
→ view never popped, stuck open → logging wrapper). no re-entrancy guard (double
Back concurrent close; safe today only via callee _is_closing immersive:1177 +
_close_player routes; hook shouldn't rely → debounce flag).
Low: redundant Container (:32-38 Control carries expand :21-39 → listener
expand=True suffices). untyped handler + imprecise callback (:15,:26 → (e:
KeyDownEvent), Callable[[KeyDownEvent],...]). installs even when useless
(on_back None → docstring "propagate to system" false; return child). PascalCase
factory misnomer (function not class; no scoping/cycling — BackIntercept w/ alias).
dual import style (both valid; ft.Control consistent).
D-pad/focus-cycling: zero D-pad keys handled (acceptable — native Flutter traversal;
but contributes nothing to TV nav + initial-focus unmanaged → first press can seem
dead). No cycling logic (N/A — framework defaults; name overpromises). Interaction
w/ use_keyboard_shortcuts implicit-fragile (Escape-in-player vs page-skip-iff-/play-
route string match — needs cross-comment).
Fix: autofocus + wrapper-drop; logged try/except + _handling flag; e.key logging
pass then exact set + stale-comment delete; None→child; types; rename+alias;
ft.Control.

## hooks/use_keyboard_shortcuts.py (112) — Needs Fixes. No high crash; chaining right.

Verified: on_mounted(fn)→use_effect(fn,[]) :78; KeyboardEvent key/shift/ctrl/alt/
meta page.py:357 + exports; on_keyboard_event Optional single-slot :655 (chaining
required); EventHandler sync|async :156 (async def valid); context.page raises
RuntimeError off-page :46-69; View.route :52.
Medium: unmount clobbers newer handler (:106-107 unconditional restore →
second-chainer mounted later wiped when AppShell unmounts first → identity guard
`if page.on_keyboard_event is _handler`). stale closures (:31-36,:86-96,:111
on_mounted [] never re-runs per component.py:337 → new controller/callbacks
ignored → document stable-refs or use_effect w/ deps / ref cell). macOS Cmd ignored
(:86,:92 ctrl-only → `or meta`).
Low: e.key None assumed str (:71,:86,:92 .lower AttributeError on malformed →
(e.key or "")). Escape omits alt (:71 → + not alt). hints lie sync-only (:33-34
Awaitable vs duck-typed sync support :83/:89/:94 → Callable[[],Any]). broad
except (:62-65 all-Exception → noop, transient disables silently no log →
RuntimeError-only or log). hardcoded "/play" (:78 View.route verified but rename-
brittle → is_player_open predicate). docstring branch drift (_set_tab(2)).
Install/chain/unmount: previous-capture + assign correct; handled-swallow +
delegate-to-previous (sync/async) correct; sync-_install return-as-cleanup correct
per session.py:731-741 + component.py:353-358 (async setup would lose it — never
convert _install to async); gap = identity guard only; double-unmount safe
(hooks cleared) but interleaved mount/unmount not LIFO-safe w/o guard.
Fix: guarded cleanup; hardened handler (key-or-"", mod=ctrl-or-meta, +not-alt);
use_effect deps option (cleanup+setup nesting-safe w/ guard); honest signatures;
narrow except; optional repeat-spam + text-input enabled predicate.

## hooks/use_storage.py (42) — Needs Fixes. Async correct; facade self-defeating.

Medium: methods close over global db_manager not self (:28,:31,:34,:37 →
db_manager property dead internally; mocking storage.db_manager no-effect →
self.db_manager). property re-exports full manager (:23-25 vs goal :3-4 callers
don't import manager → either complete facade or remove hatch; current
use_storage().db_manager.* bypasses review). lossy add_custom_channel (:36-37
drops group="Custom" manager:198 → callers can't set). silent duplicate (:33-37
manager dedupes by URL :187,:201 → None; facade None → dialog toasts success on
no-op → bool).
Low: @dataclass misuse (:19 no fields; misleading eq/repr → plain class + slots).
get_setting wrong type (:30 str|None vs manager Any :178-180; non-str default lie;
X|Y needs 3.10). set too narrow (:27 value:str vs manager str(value) :174 → Any).
per-render Storage() (:40-42 new identity; harmless stateless today; footgun in
effect deps → singleton). docstring typo; __all__ + validation missing.
Coverage 4/18 (set/get_setting, add_playlist/channel; missing get_playlists/
customs/clear/favorites/history/init/close/liveliness/sync-get_history_entry_sync
→ leak forced). Sync contexts have no path (manager sync getter exists; facade
none). Fix: plain slots class, privatize-or-complete manager access, self-
delegation, corrected signatures (Any, group param, bool returns — preferably
manager returns bool directly), module singleton, missing pass-throughs-or-
documented-minimal, typo+__all__.

## state/app_state.py (10) — Pass. No bugs; wiring correct.

Verified create_context(default)/use_context + Observable subscription incl.
default-value path (use_context.py:106-108), exports, singleton, provider mount
(main:214 ControllerMethods only — AppStateCtx intentionally unmounted; default IS
singleton + still subscribes). Shared by 5 use_context call sites.
Low: import-time singleton binding (reset() in-place safe today; future
`state = AppState()` reassignment diverges). __all__ re-exports raw singleton
(legitimizes `from core.state import state` inside @component → no subscription;
file correct, invites bypass).
Recommend: docstring (no provider by design; components must use_context; never
direct-import in @component); __all__ ["AppStateCtx"]; optional
ContextProvider[AppState] annotation.

## state/controller_ctx.py (78) — Bugs Found (slots wrong; Flet usage right).

Verified create_context/use_context/ContextProvider(value,callback) 1.0.1 +
runtime version + main:214 call-protocol match. collections.abc subscripting OK
(py3.14 floor).
High: H1 pop_modal slot zero-arg (:63 _noop_async_close_modal) vs real
main:328 (self, name) wired main:208 → default path pop_modal("x") TypeError +
real path pop_modal() TypeError. Copy-paste from close_modal (:64 correct
zero-arg). Fix _noop_async_pop_modal(_name="").
Medium: M1 refresh_channels too narrow (:59 [] vs real main:480 (force=False)
wired :204; home:266 refresh_channels(force=True) works real, default-path
TypeError defeating docstring :9-11 → (*a,**k) tolerant noop or ... protocol).
M2 play_stream too narrow (:60 (str,str|None) vs real main:504
(url,title,referer,headers,from_deep_link); today (url,title) only — first
referer caller breaks → ... or exact optional-kwarg protocol). M3 shared mutable
default (:75 global instance; use_context returns default by reference; AppShell
:65,:77,:81 mutates open_search/go_home/on_non_home_tab per render → no-provider
unit-test leaks across tests/renders). M4 open_search annotation (1-arg) vs
default lambda optional (:65; harmless + repr-unfriendly; same :70).
Low: inconsistent noop style; docstring mount-timing (provider inside render
callback main:214, not "before page.render"); check_for_updates ... vs precise
neighbors (use ... uniformly or exact); unannotated create_context generic.
Correct slots: pop_views, push_modal(name), close_modal(), go_home/on_non_home_tab,
check_for_updates/open_version_dialog (signatures match; async awaited at all
call sites; sync called directly).
Fix: tolerant noops (*args,**kwargs) or exact protocols; copy-not-mutate in
AppShell (dataclasses.replace per render) or private-default + do-not-mutate doc;
named noops; docstring timing; explicit generic.

## utils/channels.py (159) — Needs Fixes. No always-crash high on clean data.

Medium: country_of passthrough (:8-9 `in`-check returns None/""/non-str violating
->str; callers mask via `if country` — fix strip+isinstance). categories_of alias+
unvalidated (:22-23 live mutable ref — caller mutation corrupts channel; None/str
→ callers :85 TypeError; copy+validate). build_favorites_set alias (:72 set→alias
not copy — mutates state.favorites; None/missing → AttributeError (getattr);
tuple→set() data loss → getattr + (set,list,tuple) filtered copy). Other
inconsistency (:55 excludes then :59 appends vs :41/:100-102 include normally →
counts/list/dicts diverge). case-sensitive dedup/count (:86,:119,:138,:156
Sports/sports/ SPORTS distinct → UI dupes; sorts :44,:58,:89 case-sensitive).
empty-string leak (:86,:119 `!="general"` w/o truthiness; canonical [""] counted).
custom leak (:133,:152 top `=="custom"` misses " Custom "; per-part :138/:156
excludes general/undefined but not custom → "custom;Sports" counts custom; strip+
case-insensitive per-part custom filter). docstring lie (:125 "sorted unique" vs
:140 most_common frequency order).
Low: module typo ("components components"); legacy group "" → "" not Global
(:10-11 callers filter — fallback Global); missing strips (canonical " USA" vs
"USA" splits); dup-url last-wins + whitespace-url passes (:63-65, no normalize);
non-str category .lower AttributeError (:86,:119 isinstance guard); non-str group
.split crash (:132,:151 isinstance); Counter imports in-fn (:94,:112,:126,:145 →
top); custom-groups/custom-counts loop dup (:124-158 second = dict(first));
None channels (all extract_* TypeError; accept-None or document).
Taxonomy correct for dual model (canonical preferred; legacy first-segment iff
country_code else Global; dedup seen+sorted; normalized full-tag multi-count
intentional; general-filtered; favorites set/list→dedup). Fix: _norm helpers +
Counter top; validated copies; getattr-broad favorites; per-part custom filter;
casefold dedup/sort; Other policy uniform; None acceptance.

## utils/favorites.py (37) — Bugs Found.

High: silent drop on no-loop (:33-37 RuntimeError→pass; sync/background/startup/
test toggle discarded, state/DB diverge permanently — log/raise/queue instead).
in-flight guard async-deferred (:17-19 check/add inside _do after create_task
yields; rapid doubles both schedule pre-run → both write; move guard synchronous).
TOCTOU lost update (:21-27 snapshot → await DB → overwrite from stale; concurrent
toggle/sync/load clobbered).
Medium: fragile import (:6 database.manager absolute; src-layout path-shim
dependent → src./relative/DI). fire-and-forget ->None (no await/return; UI lags
to post-DB state update; failure invisible :28-29 log-only, no callback/future;
duplicate-key divergence unreconciled; cancel-between-write-and-state diverges;
no timeout/Cancelled handling).
Low: no url validation (empty/None/space → DB; str unenforced); state untyped +
favorites-assumption (background-task AttributeError invisible); exact-match no
normalization (trailing-/case/query dupes + failed removes); module-global set
unsync (thread/loop unsafe; server multi-session leak); create_task handle
unreferenced (OK w/ in-_do handling, but closed-loop RuntimeError from create
itself unhandled).
Toggle-in-isolation correct (in→remove else add); sync/async contradictory (sync
def requiring loop or silent no-op — run_coroutine_threadsafe or raise); errors
server-logged user-invisible, worst case not even logged.
Fix: sync guard + Task|None return + async core (validate+strip, in-flight sync,
get_running_loop or raise/log+discard, _toggle try/finally discard + optimistic
or re-read + idempotent apply); or async toggle_async→bool + thin sync wrapper
(optimistic UI + rollback + snackbar); URL normalize; db_manager inject; per-state
lock/compare-set.

## utils/notifications.py (161) — Bugs Found. Ctor kwargs + is_mobile correct.

Verified SnackBar DialogControl, show/pop/_remove_dialog, overlay vs Dialogs
containers, context.page raises off-callback, is_mobile (IOS/ANDROID only, excl
TV) matching comment.
High: dialog-lifecycle bypass (:75-85 overlay.append + open=True + page.update;
supported = page.show_dialog → open+_prepare(parent weakref + dismiss wrapper)+
_dialogs + _dialogs.update + auto-remove; docstring example show_dialog(SnackBar);
overlay is distinct container; wrong scope update). unbounded growth/no queue
(:69-87 new SnackBar per _show, never closes/removes/pops; no reuse/cap/dismiss
cleanup (show_dialog-only); rapid notify stacks/leaks; bare except hides).
Medium: fullscreen double-show (:123-127 docstring admits SnackBars invisible under
native fullscreen yet queues one anyway → wasted + persist-stale on exit + 4s
auto-dismiss unseen → exclusive or deferred). global toast race (:22-26,:32-40
single slot; second player mount overwrites; first unregister clears live →
per-page weakref dict or identity-guarded unregister). silent failures ×3
(:58-66,:86-87,:105-106 bare passes hide misuse/detached-update/context errors →
debug/exception). stuck toast no-loop (:115-120 RuntimeError→pass but returns True;
visible toast, no hide scheduled → sync-hide or page.run_task, no True).
Low: ambient context.page (:71-74 raises off-callback; background/service drops
caught-bare; no page param unlike page_has_ads/premium_unlocked_message → add
page=None). fire-and-forget cancel (:51-55 handle dropped; benign but
unobservable; rapid interleave).
Overlay/queue/lifecycle: wrong container; none; broken (no dismiss wrapper/removal;
open=False/removal never; persist=timeout-only not cleanup). Props valid
(content/bgcolor/show_close_icon/FLOATING/HORIZONTAL/persist).
Fix: show_dialog + reused instance (close-previous first) or single mutated
(show_dialog once); _dispatch(page=None) (page-or-context; fullscreen toast-only
+ optional exit-replay); no-loop sync-hide; weakref per-page chip + identity
unregister; logged excepts; duration param + page param; Text max_lines ellipsis.

## utils/sfx.py (43) — Needs Fixes. No high crash (all swallowed :29-32).

Medium: leak-if-start-throws (:27-28 constructed then startTone throws → bare
return w/o release; AudioTrack leak). unguarded scheduled release (:36 call_later +
:42 Timer propagate Java double-release/dead-AudioFlinger into loop/timer as
unhandled → safe_release try/except). per-tap construction (:27/:36 anti-pattern
vs docstring; rapid taps churn + RuntimeException creation-failed → lazy singleton
+ lock, teardown-only release).
Low: STREAM_SYSTEM 80 (TV/silent muted; MUSIC tracks user vol; 60 conventional).
1.0s hold for 80ms tone (→0.3s). Timer non-daemon (shutdown +1s; daemon=True).
threading import in-fn (→top). logger unused (silent except → debug). startTone
bool ignored (False = busy/in-call, currently success-indistinguishable).
Usage correct (autoclass names; (int,int) ctor; startTone(int,int); pyjnius
ctor idiom). Thread-safe stateless (concurrent safe; JNI hop caller→loop/Timer
works via auto-attach; same-thread or singleton+lock preferable). Release
exactly-once scheduled (either path never both; bound-method keeps alive; loop-
close-in-window skips — untidy, harmless on death).
Fix: construct+start guarded (failure→release+return); _safe_release + 0.3s both
paths (daemon timer); top import + debug log; MUSIC/60; singleton+lock best.

## utils/theme_utils.py (35) — Needs Fixes. No Flet misuse (ThemeMode/Light-Dark/
update/platform_brightness/set_setting signatures verified).

Medium: silent persist drop (:30-34 RuntimeError→pass; sync on_click/on_change
callers header:51-52/settings:437-440 depend on loop-in-handler; failure = theme
resets next launch, no log/fallback). partial repaint (:19-20 theme_mode+update
swaps Material theme/dark_theme main:81-82 but custom AppColors snapshots stay
until subtree rebuild; callers rebuild local only via use_state; other screens
stale → document rebuild duty or on_toggled param / central invalidation).
Low: private _is_dark cross-module (:15,:17 deferred + underscore → public is_dark
+ top import; no cycle). unheld task (:32 no ref/done-callback; exit-before-flush
lost — manager flushes only on close). no return (callers re-query _is_dark
race-prone duplication → return ThemeMode/bool). deferred import unnecessary.
Toggle correct (SYSTEM→platform_brightness; None→light implicit-acceptable; write
always explicit dark/light, never system → one toggle leaves SYSTEM-follow by
design, no path back). Round-trip correct (main:130-134 restores DARK/LIGHT else
SYSTEM default; corrupt → SYSTEM safe).
Fix: return new_mode; public is_dark + top import; RuntimeError→warning+fallback
(run in thread/minimum log); rebuild-duty doc or on_toggled/invalidation; held
task + done-callback or async variant; optional tri-state/set_theme_mode(mode).

## Inits (8 files + missing channels/__init__) — Fragile but working.

src/__init__ (1-line comment): OK trivial (add docstring/version if installable).
components/__init__ (24, 10 absolute imports + __all__): absolute (src-on-path
dependent; duplicate-module risk; → relative); eager heavy imports (cost + cycle
risk w/ channel_grid→channel_card/empty_state); incomplete (banner_ad/
focus_styles/header/version_dialog/player/ missing → consumers fail despite
existing). player/__init__ (3, relative ImmersivePlayer + __all__): OK BEST —
template; document controls/handlers exclusion deliberate.
core/__init__ (0B empty): OK but inconsistent (14 modules, zero facade → curated
re-exports+__all__ or empty-by-design docstring).
hooks/__init__ (14): absolute fragility; private _default_filters exported (leak;
home imports it directly — confirming use); missing reconcile_filters (home
imports from module, absent init) + use_autofocus + use_keyboard_shortcuts
unexported → relative + drop private + add missing or document exclusions.
screens/__init__ (12, 4 absolute): absolute fragility; incomplete (6 dirs, 4 listed;
recently_watched + search missing; app_shell local-imports SearchScreen proving
stale).
state/__init__ + utils/__init__ (0B each): OK but missed facades (2 ctx types + 5
modules all deep-imported; stable re-exports recommended).
MISSING src/channels/__init__.py (INP001): only dir without one (normalize,
provider + pycache); implicit-namespace resolves by sys.path luck, tooling-
sensitive (packaging/type-checkers/Ruff INP001/runners) → add empty/facade to
match tree.
Convention: thin relative facades everywhere (player template) OR empty inits +
deep imports — pick one; fix hooks private + channels missing.
