# 24 — App Audit: Services (18 files)

## ad_service.py (390) — Bugs Found. REPORT ONLY (no patches w/o go).

High: L27 annotation `fta.InterstitialAd|None` evaluates at runtime; except-Import
branch fta undefined → AdService() crashes w/o flet_ads instead of disabling.
L290 vs L204 consent inconsistency (preload respects _can_request_ads; show guard
checks only _HAS/premium/mobile → can show when UMP said no). L303/L374-377 leak +
wrong return (preloaded-timeout nils ref w/o services.remove; on-demand timeout
leaves fresh_ad in services; ad_shown=True set BEFORE await show → failed show
returns True). L59/L141/L162/L184/L206/L290 suspected page.platform.is_mobile()
misuse (only other check version_dialog:73 uses == PagePlatform.ANDROID; if enum
has no is_mobile method every guard raises; gather_consent masks via except→allow,
banner/show guards outside try propagate).
Medium: _ad_loaded_event replacement race (:202,:216-223 new Event per preload;
lambdas resolve at fire-time; waiter on old hangs to 10s). error path orphans
waiter (:239-248 tuple; first raise skips event-set). single _retry_task slot (:248;
overwritten, prior never cancelled; close cancels latest only). _handle_close races
+ run_task contract (:268-287 nils both refs — preload assigning between show/close
loses ref but stays in services; :279 run_task zero-arg assumption; :284 kwargs
support unverified vs main run_task(fn,*args)). on-demand handle_close drops chain
(:351-359 no on_close → next background preload loses caller). 30s close-wait
returns True while ad open (:312-322; caller resumes video under interstitial;
same on-demand 10s). get_native_style_ad not native (:146,:167,:188 BannerAd 300x250
w/ banner ID; NATIVE_ID :23 dead + misleading).
Low: triplicated banner ctors; expand=True unbounded-height risk (:113);
on_error lambdas log-only; _consent_manager never removed; close() never resets
_is_shutting_down/wakes wait_fors/cancel-awaits.
Concurrency: no show reentrancy guard (double-show same object); close doesn't stop
in-flight waits; retry respects shutdown at one checkpoint; no CancelledError
handling (unlike hls_proxy).
TV note: if is_mobile() true for ANDROID_TV, every playback fetches unfillable ads
→ wasted requests + timeout-path dependence.

## banner_ad.py (60) — Needs Fixes. Failures degrade to empty Container.

Medium: same is_mobile risk (:17; wrapped try/except → fails closed, but gating
rests on unverified API). throwaway AdService(page) for unit ID (:32-33; full
service + L27 crash risk; use AdService.BANNER_ID class attr).
Low: fixed 320x50 (no responsive; narrow overflow); on_error debug-only, no
retry/placeholder; Container style dupes _create_ad_container (two truths);
no dispose needed (plain Control).
No concurrency (sync builder). Same TV note (per-build unfillable load if TV=mobile).

## http_client.py (28) — Needs Fixes.

High: global close_http_client no ownership (:23-27; shared singleton; any holder
across close gets closed client; in-flight fails. Single-owner + shutdown-only
discipline required).
Medium: unlocked lazy init race (:8-20; concurrent first calls → N clients, N-1
leaked; lock or eager init). pool=2.0 aggressive w/ max 100/keepalive 30 (:12;
slow nets surface PoolTimeout not read timeout; smaller caps + generous pool).
Low: no default UA (bare python-httpx blocked by some origins); no http2 (hls_proxy
has it — inconsistent); follow_redirects 20-max fine; verify default-true correct
(inconsistent w/ proxy False).
Fix: asyncio.Lock creation or refcount/owned close (documented shutdown-only);
UA default; mobile-tuned limits; one HTTP/2 policy.

## hls_proxy.py (623) — Bugs Found (best-constructed of batch otherwise).

Bind-fail cleanup (:149-154), 2s wait_closed (:174), CancelledError re-raise
(:586-589), Range forward (:328-330,:569-576), urljoin, variant clamp (:381-382)
correct.
High: verify=False upstream (:137; MITM all playlist/segment/key fetches → True or
per-host). _send_response reason table missing 502+ (:599-612; :363,:559 send 502,
:367-373 forward arbitrary → "502 Unknown" wire; strict players reject).
Medium: malformed input hangs player (:297,:302,:307 b64 raises / non-dict headers
JSON update raises → outer except :335 sends NO response, finally closes → player
waits to timeout; → explicit 400s). fetch_master swallows status (:226-238
non-200/no-client/exception → None; verify/UA differ from proxy path → blocked or
indistinguishable 404 vs netfail). hand-rolled server no read timeout/size cap
(:258-342 readline no timeout = Slowloris; no concurrency cap; any-method proxied
as GET :552). .m3u8 substring heuristic (:525; query-signed manifests w/o .m3u8
→ /segment passthrough unrewritten, relative URLs break → Content-Type-aware).
EXT-X-SESSION-KEY not rewritten (:511-513; only KEY/MAP/MEDIA proxied → session-key
URLs leak original w/o Referer). narrow excepts (:335-342,:586-597 OSError beyond
Reset/BrokenPipe e.g. ConnectionLost propagates; build_request invalid-URL hangs).
Host override inconsistency (:217-224 vs :412-420; rewrite strips Host
case-insensitively, initial lets caller override Host/UA/Referer unchecked →
broken H2 :authority).
Low: stale Chrome/120 UA (:18); http2 needs h2 extra or ImportError; start() log
claims H2 for local socket (actually H1; H2 upstream-only); fetch_variants +
fetch_audio double-fetch no cache; stop() swallows CancelledError (re-raise) +
"stopped" even if never started; referer/headers in local URL (log/history
exposure); IPv4-only; resp.text charset guess; empty H2 reason_phrase.
Concurrency: stop() during streams closes shared client under passthrough (abort
expected; new conns 500 via None check); port=None (:184) prevents stale URLs;
double-start safe; in-flight rewrites racing stop() can emit None-port URLs (narrow,
local).
Fix: verify on (+per-host noqa); 502/503/403/416 or echo resp.reason_phrase; 400s
on bad b64/JSON; read timeout + header cap; SESSION-KEY rewrite; Content-Type
fallback routing; default UA in fetch_master; status-aware results/raise; re-raise
Cancelled in stop(); document query-string auth exposure.

## device_info.py (38) — Needs Fixes. Never raises; contract holds.

Medium: fragile Build.VERSION.RELEASE/SDK_INT (:22,:26; inner is Build$VERSION;
local_scanner:394 uses $ form; AttributeError → whole try skipped → Android loses
Device line though MANUFACTURER/MODEL available → per-field or $ form). all-or-
nothing block (:19-29; one bad field drops whole line → partial better). debug+
exc_info on expected desktop path (:29; called every terminal compose; DEBUG
captured → self-polluting log dump → one-time no-traceback debug).
Low: OS line always (Android Linux host noise); em-dash (adb paste → ASCII -);
except pass around is_tv_device (redundant, at least debug); None/empty → "None
None" (or unknown); no cache (autoclass per call; _compose per refresh/copy).
pyjnius/Build/fallback verified correct (lazy import; autoclass names; desktop
no-JVM caught; tv_detect tri-state; src-on-path consistent).
Fix: $VERSION + per-field getattr unknown + module cache; no-traceback one-time
debug; None normalize; ASCII dash; optional Python version line; TV line only if
Android resolved.

## iptv_service.py (34) — Needs Fixes. No high crash (local client, user URLs).

Medium: catch-all + return [] (:24,:28 swallows Cancelled + Timeout + HTTP + parser
bugs; breaks cancellation; "dead" == "empty" == "parser bug" to caller; comment
"never silent" false to caller). unbounded resp.text (:21-23 user URL; no
Content-Length/cap; OOM/loop stall on huge playlist). no error identity (:16/:30
both → list[dict]; ERR_LOAD vs "0 found" indistinguishable).
Low: Timeout(20,connect5,read15) leaves write/pool 20s (overrides shared pool 2.0;
specify 4-tuple; no total deadline — slow drip exceeds 20s wall). no exc_info
(:27); no URL validation (empty/space/non-http to client.get); resp.text charset/
BOM (→ utf-8-sig + replace); sync parse on loop (to_thread above threshold).
Fetch/timeout/redirect: get+headers+timeout correct; per-req override values
reasonable; redirects inherited True correct; raise_for_status needed; post-check
erased by catch-all.
Fix: narrow except (HTTPError/ValueError/UnicodeError) + raise PlaylistFetchError
(preserve identity); _MAX 5MB + len(content) check + content.decode utf-8-sig +
to_thread parse; full Timeout(connect5,read15,write10,pool5); URL strip+scheme
ValueError; "Custom" named const; lazy-singleton race guard.

## kiri_license.py (373) — Bugs Found (licensing ship-blockers).

High: revocation not durable (:286-293 _query drops memory on status_refusal but
never clears SETTING_TOKEN → next boot apply_cached_token re-verifies old token +
re-unlocks; same TokenRejected :314-317 + non-active-without-token :336-352; only
token+non-active :327-335 clears). apply_cached_token lies (:159-183 docstring
"rejected cleared", code clears claims only → bad token fails every boot; needs
_store(token="")). single LicenseUnavailable string erases refusal vs transient
(:42-43 no status/is_refusal → premium_service:216-226 polls 15min on hard
400/403/404, burning 20req/60s budget). non-string token crashes (:305 .get
uncoerced → :309 .split AttributeError; coerce like recovery_id/product).
Medium: fetch_catalog missing isinstance(dict) (:208 vs :233-234/:302-303 guarded;
list/None JSON → AttributeError). unwrapped float() (:203,:239 outside try;
"free" → ValueError not LicenseUnavailable → UI crash). status_refusal incl 400
(:53; 400 = client bug not entitlement-invalid; de-premiums on app bug → (402,
403,404) only + spec-check 401/410; 429 exclusion correct). refresh/unlocks
divergence (:89-90 text-only vs :147 claims-required; :345-347 effective-claims;
fresh refresh active+None → unlocks True but unlocked False; premium_service:227
requires both — future unlocks-only callers fooled). no retry + single-404
aggressive (:191-199,:271-280; transient 404 drops valid unlock → 1 retry or
consecutive-failure gate for restore/refresh).
Low: _apply bypasses _notify_change (:154-155 vs :260-263); URL rstrip missing
(:192,:217,:273 trailing-slash break); checkout no strip/lower validation (:213
empty email → server 400); catalog cache no lock (double-fetch trivial);
price_label rstrip works (0→"0"; Decimal nicer).
Flows: catalog correct not-to-revoke + caches (malformed-item poisoning + missing
dict check gaps); checkout correct not-to-revoke + persists only after url+recovery
validated (input/shape gaps); restore ordering correct (durability fail);
status reuse-claims correct only if apply_cached ran. Timeout scalar 15 loosens
shared 10/5/8 (legal, undocumented); no per-stage/retry/backoff; refusal shape
right spirit, 400 wrong.
Fix: status_code+is_refusal on exception + _store(token="") on every revoke/
reject/non-active; refusal (402,403,404) + abort-vs-retry exposure; isinstance +
float-try + token coerce; input strip + rstrip(/); _apply→_notify_change.

## license_token.py (227) — Needs Fixes. Crypto SOUND, no forgery.

Verified: P-256 params (:30-35) correct; _ecdsa_verify textbook (e=SHA256,
w=s^-1, u1/u2, X check :112-129; range 1..N :117; 64B raw WebCrypto :113/:149);
signed ASCII payload_b64 segment (:182-185, matches WebCrypto); _scale
double-and-add + infinity (:132-144); claims iss/app/status/exp (:200-213;
exact iss/app, active|grace, exp fail-closed no leeway — good).
Medium: unauthenticated JSON parse before verify + no size cap (:174-176 attacker
b64 → b64decode+loads pre-verify; huge = DoS → decode, verify, then loads; cap
~8k/4k). paid_through unvalidated (:223 int|None downstream TypeError → validate
int-or-None like exp). status reason attacker-influenced (:207-209 str(or"") →
"123"/"{...}" breaks UI match + log injection → fixed "inactive_status" + raw in
detail). SPKI suffix-only (:95-109 len≥65 + der[-65]==04 + on-curve; accepts any
blob ending 04||X||Y; no 91B length/OID/0≤x,y<P → strict). token type unchecked
(:167-169 `if not token` then .split; bytes/int → AttributeError not TokenRejected
→ isinstance str check).
Low: v `!=1` accepts True (True==1; `is not 1`/type-int check). issued_at or 0
(:224 missing → 1970; require int, reject future + exp<iat). now unvalidated
(:212 str/NaN → TypeError; finite check). pow -1 ValueError on zero denom
(unreachable valid, malformed Q → 500 not False; try/except → False).
_verify_signature bool but raises bad_public_key (:147-151 doc/type lie).
ent/product/scope/mode coerce 123/{} → "123"/"{...}", missing → "" (require
non-empty security fields). no strip (trailing \n → bad_signature). nbf ignored
(future Worker nbf accepted early). dead logger/_point_add None.
Fix: strip+isinstance+size caps; verify-then-parse; strict claims (v is-int-1,
paid_through/iat types, finite now, non-empty security fields, nbf check);
full 91B SPKI + range; fixed inactive reason; EC-math ValueError→False.

## liveliness.py (61) — Needs Fixes. LRU/TTL basics work.

High: clear() never notifies (:42-44; type Callable[[str|None],None] implies
None=invalidate-all but never sent → UI stale after clear). _dirty unbounded
dupes (:35 every set appends same url/value; undrained → unbounded + redundant DB
writes).
Medium: get() doesn't refresh LRU (:18-26 vs :30-31; hot read-evicted by cold
writes). load_from_db size/order wrong (:55-56 `>=` counts overwrites; arbitrary
items order, no ts sort, no move_to_end, silent tail drop). re-entrant sync
callback + swallowed errors (:36-40; subscriber get/set/clear → recursion; except
pass hides bugs). no thread safety (OrderedDict+list mutated probe+UI threads,
no Lock → RuntimeError/lost updates on iteration).
Low: TTL boundary (> vs <; == valid in get, dropped in load); max_size≤0 crash
(popitem on empty); wall-clock TTL (NTP jump → monotonic; wall only for persisted
ts); int(now) dirty vs float cache (round-trip drift); missing ->None (set,
load_from_db); no input validation (empty url, non-bool, malformed tuple).
Subscription: SINGLE slot (:12,:14-16; second clobbers first silently; no
unsubscribe handle; setter non-optional vs field None). set() notifies per-write
correct; clear/load never notify (None contract never sent); no coalescing
(N sets → N callbacks); exceptions dropped.
Fix: clear→on_change(None) guarded+logged; multi-subscriber list + unsubscriber
(or set(None) clear); dirty dict/coalesce + cap 5000; get move_to_end; load sorted
ts-desc + skip-expired + overwrite-aware + move_to_end; threading.Lock (invoke
outside); validate init (max(1,..), max(0,..)); monotonic TTL; finite/typed checks;
log callback exceptions.

## liveliness_store.py (107) — Needs Fixes. Cache-class, no durable loss.

Highest: save_batch crashes on one malformed entry (:99-105 unpack + float(entry[1])
Index/Type/Value → aborts whole batch → probe checker). (Missing-file vs corrupt
both None → crash-on-corrupt drops batch.)
Medium: migration clobbers concurrent save (:68-82 _read+_write no lock vs :93-107
merge under lock → interleave overwrites fresh verdicts with stale DB copy).
blocking _read under lock (:97 sync file+JSON on loop thread holding lock;
defeats to_thread _write :107 → to_thread read). fixed .tmp + asyncio-only lock
(:62-65 same-dir replace right pattern/EXDEV-safe; but shared .tmp races, no
cleanup, no fsync → docstring overpromises; mkstemp+replace+finally-unlink).
Low: STORE_PATH import-frozen (:26-31; tests/late env stale → _store_path() fn).
corrupt retries DB migration every load (:46-54,:70-72 None for both → debug+DB
hit each boot → distinguish missing→migrate vs corrupt→{} /quarantine).
blocking _write in async migration (:81). relative fallback CWD-fragile (:30).
lazy asyncio.Lock (:36-43; multi-loop/test RuntimeError pre-3.10; per-loop/thread
lock or full to_thread RMW). unvalidated migration shape (:80 2-elem assumption →
persisted then M1 crash).
Persistence/atomic/lock: placement (cache dir, 30d prune, one-shot DB import+clear)
Pass; atomic partial (pattern right, unique-tmp/cleanup/fsync/IPC missing);
lock needs-fix (load bypasses, read blocks, asyncio-only).
Fix: _coerce_entry drop-None; merge migration under lock + validate legacy;
full RMW in to_thread under lock; mkstemp + fsync + cleanup; _store_path();
missing-vs-corrupt sentinel + warn-once.

## local_scanner.py (501) — Bugs Found. Walk sound; MediaStore broken on 10+.

High: exists-filter defeats scoped storage (:285 path+exists drops valid rows whose
stat denied though ContentResolver open works). _data deprecated/NULL on 30+
(:268-274 + :285; must use _ID + ContentUris + openFileDescriptor; duration/
thumbnail never populated — projection omits duration). list projection
PyJNIus failure (:276 (list) unreliable → String[]/toArray; commonly throws
Invalid arguments, swallowed :304-305 debug → silent [] on device; must Java-array
+ warning). resolve_saf_path primary-only (:240-249; SD/home/non-primary/document
URIs fall through returning content:// treated as POSIX → Path/remove fail;
hardcodes /storage/emulated/0, breaks multi-user /10, split("primary:")[-1]
filename break).
Medium: fallback never fires (:109-122 same stat fails; NotADirectory unlogged).
O(n²) dedup (:149,:203-206 → set). key normalization (:197/:141 trailing
//symlink/case dupes → normpath/normcase; :195 str== fragile → phantom folder).
mid-file imports (:237,:471 + :473 shadow logger → top). POSIX home walk (:469-486
entire ~home recursive — slow/battery/invasive → ~/Movies/Videos/Downloads/DCIM;
Termux check fragile). delete swallows RecoverableSecurityException (:335-352
debug+False → caller can't distinguish retry-request vs hard fail → tri-state).
desktop JNI every scan (:209-210 gate try-import/platform once; off UI thread —
exists-per-row ANR). dead _format_* (:82-100 raw stored, never formatted).
Low: _is_system_dir never fires off-nt (document); positional getLong/getString
(fragile → getColumnIndexOrThrow); full-projection exists-query (→["_id"]);
pending_intent/content_uri unchecked (:402-408); API29 consent gap (:395 <30
returns False, needs Recoverable path); deprecated startIntentSenderForResult +
onActivityResult wiring for 0x4B54 unverified (else poll); nameless entry when
name+path null (handle after High fix).
Query/SAF/delete: signature right, types/deprecation/exists wrong; SAF incorrect
beyond primary (no DocumentsContract, .. unsanitized); delete 3-step design
correct (owned → createDeleteRequest on android.provider.MediaStore :367-371
correct class → exists tri-state bool|None :424 correct; FileNotFoundError→True
fallback correct) with exception-type + result-wiring gaps. Merge preserves
content_uri (:219-228 good).
Fix: ID-only discovery (ID/DISPLAY/SIZE/DURATION/MODIFIED + withAppendedId +
lazy FD; drop exists gate); Java array + warning; SAF urlparse (primary→
/storage/emulated/0 else "" + normpath + .. reject); seen-set + normcase keys;
targeted POSIX dirs + dedupe; top imports; walk onerror debug + sortOrder/limit;
Recoverable→None/raise.

## permission_service.py (66) — Needs Fixes. Core flow matches installed API.

Verified: PermissionStatus 6 + STORAGE-deprecated-13+/VIDEOS-13+ (types.py);
get_status/request→Optional + open_app_settings bool (permission_handler.py);
Service auto-register via context.page; page.services property; FilePicker docstring
pattern confirms services.append usage.
Medium: LIMITED-as-denial (:44-58; Android14+/iOS partial usable grant → False +
empty scan; accept LIMITED). no get_status pre-check (request every mount+pick →
re-prompt + OS escalation to permanent on 11+; get_status first, request iff
DENIED/unknown). no PERMANENTLY_DENIED/open_app_settings (re-request ignored
forever, no recovery; expose tri-state + Settings action). attach w/o update +
fragile cache (:35-40; no page.update after mount → first request None/raise;
page.permission_handler attr + auto-register double-register risk → reuse via
services search + guarded update). end-to-end denial lost (local_screen ignores
bool; file correct in isolation — flagged for status-check completeness).
Low: comment "Android 10 and below" wrong (STORAGE <13; only 13+ deprecated).
None conflated with denial (:44-63; log "declined" even on None/exception; log
actual status). fail-open/fail-closed inconsistent (:12-13,:25-26 True on gate
exception vs :64-66 False outer → gate exception skips prompt). IOS attempts
Android VIDEOS→STORAGE (harmless wasted round-trip; Android-specific flow).
no timeout (undismissed dialog hangs _on_mount; wait_for 60).
VIDEOS→STORAGE order correct (13+ fallback harmless no-op denial; <13 VIDEOS
raises then STORAGE works). Status incomplete (accept LIMITED; distinguish
PERMANENT/DENIED/None; get_status fast path). Settings redirect absent (tri-state
+ open_app_settings UI).
Fix: get_status-then-request both permissions; LIMITED success; tri-state return
(granted/denied/permanent) + local_screen branch (skip+rationale / Settings btn);
services-search reuse + post-append update; status logging; comment fix; gate to
(ANDROID,ANDROID_TV) or skip VIDEOS on iOS; wait_for; honor return at call sites.

## premium_service.py (288) — Needs Fixes. No entitlement bypass.

Verified vs kiri_license/channel/state/notifications + main/settings call sites.
Medium: reconcile_loop no supervisor (:188-191; reconcile_if_due can raise —
recovery_id :141 outside try, DB transient → hourly task dead forever). watcher
only LicenseUnavailable (:216-226; _store/verify bugs kill 15-min watcher early;
reconcile :147-151 catches generic — watcher must too). hourly calls debounced not
forced (:191 reconcile_if_due; resume-reconcile <60s before tick skips hourly w/o
catch-up → loop reconcile() directly). _last_reconcile_at before work + unguarded
recovery_id (:140-141; DB exc → stamped + bubbles to run_task).
Low: Play load_local silent no-notify (:112-116 stale True never broadcasts).
_recompute always-notify (:70-76 hourly no-op fans out). completed watcher never
clears task (:216-240 stale done ref; harmless via done() checks). status in
(active,grace) dupes LicenseStatus.unlocks (:227 vs kiri:89-90). kiri_checkout
notifies w/o entitlement change (:267 license.checkout never on_change →
gratuitous rebuild). _premium_disabled info on hot path (:164,:174,:200 every
RESUME → debug). kiri_check_status dead? (:281-287 no callers; /status non-issuing
can't re-arm expired per reconcile docstring :132-136 → delete or document).
missing return annotations (:249,:262,:273,:281).
Reconcile (:172-191) start/stop/refs + run_task correct; supervision + debounce
gaps. Watcher (:193-240) service-owned (survives nav) correct; ~180 restores/15min
~12/min under 20/60s budget but headroom thin if catalog/restore race; success gate
(active|grace + unlocked) correct (verified token required); gaps generic-death +
no jitter/backoff + no early-exit when parallel restore unlocked. Listeners
(:78-92,:70-76) dedup + copy-iterate + per-callback try correct; bound-method eq
makes main:119 dedup work; closure + on_mounted cleanup correct; risks churn +
debug-swallow + sync-only unenforced (async cb → unawaited).
Fix: loop try Cancelled-raise + Exception-warn (never dies) + reconcile() direct;
recovery_id in try / stamp-after; watcher except Exception debug+continue
(Cancelled re-raise) + backoff/jitter; clear task on done + stop on restore-unlock;
notify-if-changed + Play-branch notify; status.unlocks use; delete/document
check_status; return types.

## tv_detect.py (65) — Needs Fixes (minor; no misclassification).

Verified leanback canonical (hasSystemFeature android.software.leanback); caching
correct (verdicts cached, None retried — avoids pinning phone if early); fallback
safe (None→False phone UI; retry allows late activity; no escape).
Medium: mActivity-then-mCurrentActivity getattr-or (:51-53; first missing raises →
continue skips second attr on same host → probe each independently). candidates
import-frozen (:15-21 getenv once; late env/test ignored → build inside _detect).
doc mismatch (:42-45 None-when-unrunnable vs :40-41 except→False desktop-definitive
→ pick one).
Low: "at most once" false (None uncached → retries; correct behavior, wrong doc).
unsync global (benign idempotent double-detect). desktop+jnius-no-activity loops all
candidates + debug per call, never caches (retry cap/TTL/negative-cache). `bool|
None` needs 3.10+ (verify p4a target else Optional). no test hook (add _reset).
Fix: per-attr probe; in-function candidates; doc sync (desktop False definitive,
None = no-activity-yet); _reset_cache; unknown-retry cap/TTL; LEANBACK const.

## update_service.py (85) — Needs Fixes. Fetch/timeout/compare sound, silent-offline.

Verified constants (APP_VERSION 2.2.0, BUILD 20, UPDATE_CONFIG_URL raw GH
version.json). Comparison integer build_number (no semver-lexicographic bug);
fallback version display-only (right); `<=` strictly-newer/downgrade-ignore
correct; timeout 4.0 + redirects correct usage (redirects REQUIRED for raw GH).
High: docstring promises announcement/notice delivery (:66-68 vs :52-55) but
server_build<=APP gate (:66-68) returns None first → same-build announcements
never delivered. Implement pre-gate announcement branch or fix docstring.
Medium: mandatory bool() (:78 "false"/"0"/1 → True → forced mandatory on string
payload → explicit parse). except Exception (:82 masks HTTP/JSON-intended +
Type/Attr construction bugs → narrow (HTTPError,ValueError,TypeError,KeyError)).
return-type mismatch (:52,:71-81 signature dict|None + to_dict but docstring
"UpdateInfo dict"; callers expecting .version → AttributeError → return
UpdateInfo|None or rename). falsy URL no-guard (:79 github_url null/"" → dialog
no-fallback; playstore "" → normalize None). unvalidated passthrough (:72,:75-77
version/title/notes non-string → downstream crash/None render).
Low: True-is-int (:67 isinstance(True,int); safely <20 today; type-is-int + coerce/
warn). missing build_number silent (:66 default 0 → no-update no-warning; warn if
publisher bumped version w/o build). info_type unvalidated (:70 typo propagates).
per-call AsyncClient 4.0s (:57 aggressive mobile/GH tail → false offline; no
reuse/retry/cache/debounce/UA/Accept).
Fix: announcement branch or docstring; strict normalize (str coerce, falsy-URL
fallback, type allowlist, mandatory in (True,1,"true","1","yes")); narrow except +
malformed warning + offline debug; UpdateInfo return + docstring; UA/Accept +
split timeout (connect5/read10/write5/pool5) + TTL cache/shared client; config_url
https-only validation.

## video_thumbnails.py (199) — Needs Fixes. Happy-path flow + discipline correct.

Verified: class strings (MediaMetadataRetriever, Bitmap$CompressFormat $,
FileOutputStream, File, Uri); setDataSource(String) vs (Context,Uri) overloads;
per-call new retriever + finally release + recycle + close (thread-safe principle);
compress(JPEG,85,stream) + boolean check; to_thread off-loop + Semaphore(2)
required-present (default pool large); return_exceptions batch (one bad won't
cancel batch).
High: model AttributeError (:41,:134-139,:164,:167,:179 video.path/size/thumbnail/
content_uri unguarded; try :37 covers modified only; prewarm no per-video try →
one bad/dict/frozen/__slots__ video aborts 40-fill). unbounded cache (:46-57 TTL
30d on-access only; no purge/LRU/cap → TV box orphans forever).
Medium: short clips never thumbnailed (:103 fixed 1s getFrameAtTime; <1s → None→
False; fallback 0/CLOSEST_SYNC). return contract wrong (:155,:171,:187,:198
"now available" = this-call successes only; pre-populated → 0; filled-gated update
couples to miscount). swallowed batch exceptions (:184-187 gather
return_exceptions then count-True; non-True dropped no log → H1 invisible).
relative fallback dir (:22-27 no env → storage/video-thumbnails CWD-relative;
desktop repo-write / Android-undefined → absolute app cache/tempfile). redundant
setDataSource (:89-100 content_uri-truthy + activity-None → try path then except
re-calls same → IllegalStateException risk; explicit branch). duplicate-extract
race (:134,:154,:82 no per-out_path lock; concurrent prewarm/same-video share
.tmp + renameTo spurious fail).
Low: key fragility (:41 `:.0f` sub-second loss, size None literal, no
normcase/abspath → symlink/rel-abs dupes). renameTo unreliable (:118-120 checked
good but cross-fs/exists/OEM silent-fail + tmp left; os.replace after close
atomic+raising). .tmp leak on direct use (:106-115 False paths no delete; cleanup
only extract_thumbnail :144-149). stream.close masking (:107-111 finally IOException
masks compress success → suppress/flush-explicit). mr=None init (:83 outside try;
ctor-throw → finally NameError suppressed only by suppress fragility).
getFrameAtTime(long) deprecated 28+ (works; add flag/fallback per M1). JNI attach
implicit (relies on pyjnius shipping; comment/assert). no timeout (corrupt file
stalls seconds; 40×/2 concurrency stalls refresh; wait_for 10 or document).
Fix: getattr guards + per-video try; mr=None; explicit source branch; frame
fallback; os.replace + in-caller tmp delete; (filled,available) return + dropped-
exception log; per-path lock/dedup; absolute dir + purge_stale(max_age,max_bytes)
cron + abspath key; wait_for timeout.

## youtube_resolver.py (485) — Bugs Found (graceful fallback hides breakage).

High: stmt_pattern 2-arg-only (:166-168 `helper(buf,arg)`; reverse 1-arg (buf)
never matches → reverse steps dropped → wrong sig → 403 all signatureCipher needing
reverse). page_response regex (:328 no DOTALL + non-greedy → multiline never;
single-line truncates at inner }; → almost always None; InnerTube refetch saves
it — fallback dead). jsUrl unescaping (:311-325 `\/` intact → client.get fails →
original URL; needs \/-replace/unicode_escape). missing n-param decipher (modern
WEB throttles &n=...; only sig fixed :476-482; page_response(WEB) reuse → ~50KB/s;
ANDROID unthrottled claim OK but reuse path needs n). _swap ZeroDivision (:74-76
n%len empty buffer → guard).
Medium: extract_video_id (:27 misses /live/, /v/, attribution, over-matches 12-char
v=; /live only via page-scrape). live scrape first-videoId (:302-304 often suggested
not live → og:url/canonical/watchEndpoint/r.url priority). XOR solver exact-string
brittle (:129-157 t=x[c[S^589]]...; rotation → legacy throw; expect frequent
breakage). helper classification (:199-214 literal reverse/splice checks vs H[]
obfuscation → [0]=/0,K/default-swap heuristics; "[None]" risk). hardcoded ANDROID
21.02.35 + b64 key (:367-372 old client → LOGIN_REQUIRED/restrictions/403; no
playbackContext contentCheckOk/racyCheckOk; no playabilityStatus check; restricted
silently fallback no-reason). progressive pick (:424-431 first itag in (22,18)
list-order not best; [18,22] → 360p not 720p; adaptiveFormats unhandled-noted).
_ALGO_CACHE unbounded (:463-469 correct key js_url; never evicted; no lock;
thundering-herd ~1MB base.js + CPU in loop). raw_h unicode_escape (:120 corrupts
non-ASCII/double-unescapes; delim_h never unescaped). URL rebuild (:478-484
qsl w/o keep_blank_values drops empties; private _replace OK → urlencode after
keep-blank).
Low: "/live" substring (:357 extra fetch for ?live= params; harmless). block_pattern
inconsistency (:153-156 \w+^\w+ vs \w+^\d+). legacy ""-only regexes (:240-248 dead
on current players). discarded _key/_pr (:455-458 wastes usable api_key/response).
cookie scope (:466 CONSENT+redirect to googlevideo risk if js_url elsewhere →
scope youtube.com). CPU parse in loop (:468 → to_thread).
InnerTube: ANDROID/UA/key shape right + currently correct unthrottled path; missing
freshness/playbackContext/validation. Primitives correct (splice/reverse/swap +
dispatch + ValueError). Parsing incorrect (reverse-arity + heuristics + brittle XOR
→ legacy ValueError → caught :470-471 silent original-URL fallback). Caching key
right; needs LRU bound + lock; no stream-URL cache correct (expire ~6h; expiry-
aware TTL only).
Fix: optional-2nd-arg stmt (reverse,0); DOTALL + brace-balance (or drop page path);
js_url unescape + prefix handling; empty-swap guard; video_id regex + len/boundary;
canonical-first live ID; explicit itag-22 preference + playability log +
playbackContext + client bump tracking; LRU(8) + lock + to_thread parse; keep_blank
+ ratebypass + n-descrambling/ANDROID-force; unified timeouts/retries + scoped
cookies.
