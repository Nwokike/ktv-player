# 23 — App Audit: Core (14 files)

## app_loader.py (164) — Bugs Found. No Flet misuse (observable + SnackBar verified).

High: H1 force refresh wipes grid offline (:66-68 + provider:112,158-170):
_channels=[] then get_all_channels(force=True) skips disk; network fail → [].
Delete lines 66-67; keep stale fallback. H2 shared dict refs mutate DB + alias
layers (:74-78,:86-87,:150 + manager:206-208 + state:54): list() shallow copies;
cc["is_custom"]=True mutates db_manager._data without dirty → next save persists
is_custom into ktv_storage.json. Copy dicts on merge; never mutate DB dicts.
H3 empty success overwrites good state (:150 unconditional set_channels) → guard
non-empty, else keep stale + notify_error.
Medium: M1 CancelledError swallowed (:98-113 gather return_exceptions + BaseException
continue) → drop return_exceptions or re-raise Cancelled. (iptv_service never raises
Exception, so only BaseException caught.) M2 malformed playlist row aborts load
(:100 pl["url"], :125 urlparse(pl["url"]) KeyError → outer except drops built-ins
too) → pl.get + skip invalid. M3 per-favorite write storm (:35-43 + manager:239-254;
50 remaps = 50 full rewrites under loading_lock) → batch remap single-lock/save.
M4 first-wins remap wrong region (:27-31 url_by_name merged order) → same-group
preference or skip ambiguous + log. M5 remap duplicates (:40 + manager:246-254;
no new_url-exists check; get_favorite_urls set dedups but get_favorites list
doesn't) → drop/merge dup.
Low: dead page_obj param; private _channels access (harms concurrent readers —
provider:214-219 serve [] mid-fetch); fragile "destroyed session" string match;
nondeterministic favorites set order; function-level imports; em-dash group name;
missing annotations.
Fan-out/gather/zip/state: free+pack fetch serial in provider (2x30s worst; gather
in app_loader for customs correct); gather preserves order → zip safe today,
strict=True defensive OK (3.10+); state mutation incorrect per H2 (fresh list,
shared dicts; state.set_channels also shallow).
Fixes: delete clear lines; guard set_channels; copy on merge; validate rows;
fix cancellation; batch remaps; disambiguate + dedup; drop/use page_obj; hoist
imports; sort favorites; overall wait_for ~60s around gather.

## changelog.py (53) — Bugs Found (safe functionally, wrong fallback).

Medium: 1. notes_for fallback returns OLDEST not latest (:52-53:
`next(reversed(CHANGELOG.values()))` on newest-first dict → 2.0.6 instead of 2.2.0;
docstring says latest). 2. latest selection implicit in insertion order, no
enforcement/helper → fragile (future append at end flips behavior silently).
Low: 3. `.get(version) or ...` conflates missing with falsy → explicit None check.
4. version not normalized (whitespace/v-prefix/"2.2" miss → stale fallback).
5. mutable global dict (Final/MappingProxyType/__all__).
6. reversed(values) obscure (3.8+ OK; iter() clearer for newest-first).
Correctness: known-version paths correct; empty-dict → "" correct; None input no
crash (hint violated). Maintainability: \n-joined strings noisy diffs; no
list[str] structure (no native bullets/count/i18n); no latest/available helpers;
dict[str,str] needs 3.9+.
Fix: latest_version()=next(iter(CHANGELOG)); notes_for strips v/normalizes,
`in`-check, fallback latest; Final + __all__ (+MappingProxyType); tuple[str] entries
joined at display; test known/unknown/empty/whitespace cases.

## channel.py (24) — Needs Fixes (no functional bug).

Medium: unvalidated untyped bare string (typo/bad CI rewrite propagates); fragile
deploy contract (build-all.yml text-overwrite, no in-file guard); mutable global
(no Final/accessor).
Low: no annotation (Final[Literal["direct","play"]]); doc-only policy (no
is_direct()/is_play() helpers); no __all__/ALLOWED set/normalization; CI path
doc-drift risk.
Model correct (two-state, default direct documented). Validation/normalization
absent (not needed for literal, required for CI-overwrite robustness).
Harden: typed Final + import-time `in` check ValueError; is_direct/is_play helpers
(+StrEnum); __all__ + ALLOWED frozenset; CI script parses/rewrites + fails job if
not allowed; unit test CHANNEL in ALLOWED.

## constants.py (235) — Needs Fixes (no import crash).

High: premium_pack_url no error handling/caching (:30-32 b64decode raises if
corrupt; re-decodes per call). KIRI_LICENSE_PUBLIC_KEY alphabet ambiguity
(:196-199 base64url chars -/_; verifier must use urlsafe_b64decode — verify +
comment + assert). CDN_HEADER_OVERRIDES mixed semantics (:170-174 suffixes vs
"kwik" substring; == vs in ambiguity; hardcoded kwik.cx Referer).
Medium: PLAY_STORE_URL vs KIRI_LICENSE_APP_ID duplication (:16/:203 → derive URL
from ID). PAGE_SIZE 24 == AD_ROW_INTERVAL 24 (:177-178 → pagination off-by-one
unless intentional + commented). LIVELINESS_BATCH 10 vs SEMAPHORE 8 (never fully
concurrent; misnamed → MAX_CONCURRENCY) + UPDATE_INTERVAL int vs float seconds.
FOCUS_ANIM ms vs *_SEC seconds (no suffix convention → 1000x risk). ERR string
contract (punctuation; ERR_PLAYBACK vs ERR_PLAYBACK_FAILED near-dup). grouping
break (KIRI block splits AD/ STREAM/LOCAL/NAME network block). missing
UPDATE_CHECK_TIMEOUT/RETRY/MAX_PLAYLIST_BYTES (remote version.json + mega index
imply unbounded download).
Low: base64 "hides URL" false security; {placeholders} no helper (KeyError risk);
\u escapes vs literals; duplicate Refresh/Activity/Add strings (dead variants?);
FOCUS_BORDER 3.5 float (int expected?); MAX_NAME_LENGTH scope + OS-255 conflict;
mutable, no Final/__all__/Enum.
Fix: lru_cache + validate premium decoder (scheme check); single-source app ID;
suffix-tuple + endswith matcher + KWIK_REFERER const; _SEC/_MS suffixes +
float secs; add missing timeouts/byte cap; Final + __all__ (StrEnum for LBL/ERR);
pin APP_VERSION from version.json/pyproject.

## country_codes.py (267) — Needs Fixes (no crash; lookup safe).

Medium: missing "gb" alias (:241 uk only; ISO uses gb; uk exceptional-reserved →
gb channels ungrouped). tvg-id contract brittle (:264-266 expects bare suffix but
docstring shows `Name.code@quality` → no parsing helper; callers must split or
silent None). `str|None` needs 3.10+ (pin or Optional). "sz" Swaziland stale
(→Eswatini 2018). generated-file claim unverifiable (no script/URL rev/checksum/
date → silent drift).
Low: str() over-coercion (None→"none", b"ua"→"b'ua'" instead of fail-fast);
mutable global (MappingProxyType/Final); naming mix (Aland vs Åland, Ivory Coast
vs Côte d'Ivoire, Cape Verde vs Cabo Verde, Czech Republic vs Czechia, Macao vs
Macau, Reunion/Réunion, Sao Tome/diacritics, East Timor vs Timor-Leste, Turkiye
vs Turkey/Germany/Spain convention); no __all__/reverse/Unknown helper.
Data: 250 keys, sorted, no dupes, case-insensitive OK; omits deleted an/cs/yu/tp
correctly; includes bv/hm/sj/um/tf (iptv-org consistent); xk Kosovo correct but
needs exception comment. Claim "asserted in test_channel_pack" needs cross-check
vs current index.
Fix: gb alias; Eswatini + naming convention pass; country_name_from_tvg_id
(rsplit(".",1)[-1].split("@")[0]); harden signature (None/empty early or strict
str); freeze map; provenance header + regen test; __all__ (+reverse index if
folder matching needs).

## crash_reporter.py (79) — Needs Fixes (won't crash app; can lose crashes).

High: same-second timestamp collision overwrites (1s resolution + "w" truncate;
likely under crash loops → unique ts+pid, mode "x"). traceback loss in handler
(:64-67 synthesizes Exception(err_msg) — type/stack/cause discarded; preserve
e.data if BaseException).
Medium: datetime.UTC needs 3.11+ (AttributeError while reporting → timezone.utc).
retention off-by-one (cleanup before write → MAX+1 steady state → cleanup after).
CWD-dependent path (no env → abspath(storage/crashes); desktop read-only/scatter).
silent OSError (makedirs/open fail → caller never knows; return path|None).
Low: get_event_loop → get_running_loop (:77); un-awaited prior handler (coro never
runs); fragile cleanup (getmtime O(n log n) + abort on missing/*.log dir; per-file
guard + isfile); ambiguous timestamp (no TZ suffix → ISO-8601 UTC); double-install
doubles logs (idempotency guard).
Coverage partial: only page.on_error hooked; sys/threading/asyncio handlers missing.
Fix: unique filenames + post-write cleanup + return path; traceback preservation;
get_running_loop; await-or-schedule prior (iscoroutine→create_task); _ensure→bool +
record→str|None; per-file guarded cleanup; app-anchored path + header
(platform/app/py/ISO ts); optional global hooks.

## deeplink.py (80) — Bugs Found (fail-closed main path; injection gaps).

High: H1 headers unsanitized (:57-76: no isinstance(dict), no str/CRLF/size/blocked
Host/Content-Length/Authorization checks → attacker link → play_stream → upstream
fetch header injection/SSRF assist). H2 file/content/absolute allowed from external
link (:26-30 via validator :26-28,:38-40) → deep-link should be network-only
(http/https + explicit rtsp/rtmp).
Medium: M1 no scheme/host gate (:17-18 accepts https://evil?url=...; caller checks
main:738 but unsafe reuse) → gate ktv + play. M2 no length cap before b64decode
(:20-26,:59; 10MB param DoS) → _MAX_B64 8192 + helper. M3 referer unvalidated
(:47-55; no URL/CRLF check; alphanumeric plaintext misdecodes as b64 garbage) →
shape check + strip. M4 title ambiguous (:32-45; plaintext tried as b64 first;
"abcd" → garbage; isprintable rejects legit \n, falls back to raw blob) → strict
charset + round-trip check else plaintext. M5 validator weak (delegated :30-36:
startswith + urlparse sans netloc; `https://`, `http://[bad` pass; no
control/space/credential rejection). M6 decoded URL not stripped/controlled
(trailing \n passes).
Low: private import (publicize is_valid_play_url); json import ×2 in fn (→top);
manual padding w/o validate=True (masks malformed); parse_qs +→space interop
(replace/document urlsafe-only); raw-JSON fallback fragile (&/= split → enforce
b64-only); log leaks decoded URL (:29 [:80] + exception route traceback);
silent fallbacks (debug logs).
Fix: scheme/host gate; _b64 helper (space→+, strip, cap, validate=True);
network-only is_valid_deeplink_url (http/https + netloc + no CRLF + ≤4096 + strip);
title round-trip rule; referer validate; headers isinstance + caps (32 keys,
64/2048 lens, str-only, CRLF-strip, blocklist host/content-length/
transfer-encoding/connection/authorization/cookie) + drop-logging; top json import;
no URL logging.

## logger_handler.py (43) — Needs Fixes.

Medium: M1 duplicate on reload (identity check; new object passes; old never
removed; shared ClassVar deque → 2x/3x appends). M2 setLevel(DEBUG) ineffective
alone (root default WARNING → DEBUG/INFO never reach emit → terminal misses logs).
M3 readers race writers (handle() holds lock for emit; get_logs/clear_logs
lockless → torn snapshot/drops/dupes).
Low: except→pass violates Handler contract (→handleError); shared ClassVar across
instances (second instance shares + clears for all); datefmt %H:%M:%S loses date;
import side-effect, no install/uninstall API, identity-not-type idempotency.
Correct single-import/single-thread otherwise (emit formats incl. exc_info; copy
return; maxlen 500 bounds).
Fix: install() idempotent by isinstance (no auto-install or type loop);
root.setLevel(min(...)); locked readers via handler lock; handleError;
instance _logs (maxlen param); datefmt %Y-%m-%d %H:%M:%S.

## logging_config.py (52) �� Needs Fixes.

Medium: M1 second call silent no-op (drops new level → runtime/test reconfig fails).
M2 raiseExceptions=False process-global permanent (hides all pipeline failures,
not just Windows teardown OSError). M3 duplicate guard exact-type (misses
pre-existing StreamHandler(sys.stderr)/subclasses → double console; split-brain
w/ logger_handler self-attach).
Low: function-local import (src-on-path fragility); two formats (console vs memory
field order; docstring "consistent" false); default DEBUG too verbose (500-ring
churn) vs console INFO pinned (undocumented); kivy/jnius dead config (Flet app
leftover); flet INFO still noisy; _configured no lock/force/reset; sys.stdout
bound at setup (late redirects/capsys/pythonw stale).
Works for single production path (main:938). Fix: setup_logging(level=INFO,
force=False) honoring level; isinstance-based stdout-dedupe; shared Formatter;
shutdown-safe StreamHandler subclass swallowing only OSError/ValueError on emit;
top/relative import; env override (KTV_LOG_LEVEL); drop kivy/jnius.

## state.py (89) — Bugs Found (works by accident).

High: H1 field(default_factory=list) without @dataclass (:1,:9,:12-14) — Field
objects as class attrs until __init__ overwrites; works only because :33-36 assign
[]. Redundant + misuse (observable supports non-dataclass). H2 custom __init__
no super + only 3 fields (:33-36; rest stay class attrs until first write → first
write sees Field-old, spurious notify; fragile to subclass/class reads).
Medium: M1 channels_hash salted/colliding/order-insensitive (:60-66 sum(hash()%10M);
reorder → same hash → stale use_memo in app_shell/home/onboarding/channel_grid).
In-process memo only, never persist/compare. M2 reset omits is_deep_link_launch
(:71-85 vs :20; test leak). M3 triple-notify per add_to_history (:48-51 reassign +
insert-touch + slice) + set_channels (:54+:60) → 2-3x re-render all subscribers.
M4 history title regression + field loss (:38-41 `title or url` discards old title
on ""; drops extra keys; mirrors manager so consistent, future metadata stripped;
DB 50 vs MAX 20 divergence undocumented).
Low: L1 .get on possibly-str entries (manager migrates strings; corrupt in-memory
str crashes); defensive isinstance needed. L2 shallow list copy (shared dicts;
ObservableList wraps list not items → in-place [0]["name"]= no notify; safe only
because app_loader always fresh-lists). L3 theme_mode dead/duplicated (:19,:81
written, never read; page.theme_mode used everywhere → sync or delete). L4 reset
~8 notifies (fine tests, noisy live).
Observable/history mechanics verified working (setattr/list/dict-op notify;
history dedup/MRU/carry/cap matches manager + player contract). Fix: @dataclass or
drop field/; order-sensitive sha256 hash incl. name; reset flag; single-assign
writes; title preserve (existing or url); isinstance guards; theme sync-or-delete;
O(n) is_favorite fine.

## theme.py (207) — Needs Fixes. No hard API crash (all ctors/enums verified).

Medium: M1 on_secondary BLACK on #0284C7 (~2.8:1, WCAG fail for Chip/FAB/secondary)
→ WHITE like on_primary. M2 ColorScheme missing brightness (exists theme.py:1111;
Flutter infers from seed → SnackBar/dialog/selection contrast drift) → explicit
DARK/LIGHT. M3 dark-fallback disagreement (_is_dark True-on-exception vs False on
platform_brightness None vs grey_dim #555555 light; SYSTEM+unknown → light silently)
→ single default + cached local. M4 private _is_dark used cross-module (header) →
public is_dark.
Low: get_surface == get_card_bg (alias one); double _is_dark calls per getter
(cache local); empty AppBarTheme() ×2 (remove/configure); untyped grey_dim/
get_glass_bg + bare except (narrow RuntimeError/AttributeError); SECONDARY ==
PRIMARY_DARK (document or distinct accent).
Verified: Theme/ColorScheme/CardTheme/NavigationBarTheme/SearchBarTheme/
PageTransitions(android,ios; linux/mac/win → ZOOM default OK, be explicit)/
focus_color/visual_density/COMFORTABLE(denser than STANDARD — reconsider for 10ft)/
with_opacity order/focus/seed+scheme redundancy (drop seed if scheme complete)/
surface_tint TRANSPARENT/scaffold-vs-surface conflation/ThemeMode/Brightness/context.
Fix: brightness both schemes; on_secondary WHITE; unified is_dark + alias;
dedupe; explicit desktop transitions; STANDARD or documented COMFORTABLE;
typed/narrowed helpers; AppBar bgcolor or removal; scaffold/dialog backgrounds if
leaving manual get_bg.

## tokens.py (61) — Needs Fixes (import-safe; constants only).

Medium: alias snapshot divergence (:50-60 SPACE_*=SPACING_* copies at import;
monkey-patch/theme-override won't follow → single namespace or __getattr__ link).
ambiguous CARD_ASPECT_RATIO 0.75 (:44 w/h vs h/w → suffixed name). hardcoded
GRID_MAX_EXTENT 160 / DIALOG 500x420 (:45-47; no DPI/relative → HiDPI/small wrong).
Low: SPACING_MD 14 off-grid (→12/16); FONT 13/15 subpixel (→12/14/16); single-name
font stacks (Outfit + Courier New fallback unpredictable → stacks); RADIUS_FULL
9999 excessive (→999/h/2); units partially documented (ms header; px/pt/logical
for rest missing); mutable globals (Final + __all__).
Correct: syntax/runtime, plausible values. Fix: canonical namespace; Final +
__all__; clarified ratio; 4pt grid; font stacks; units header; scalable dialogs/
grids; optional FONT_WEIGHT/LINE_HEIGHT/OPACITY/ELEVATION/Z (colors split
intentional? confirm).

## url_validator.py (53) — Bugs Found.

High: network branch no-op (:30-36: urlparse rarely raises → any whitelisted-prefix
string True; `http://`, `https:///`, `http://?x=1`, whitespace/newline forms pass;
no hostname check). no whitespace/control rejection (:23,:33; space/\t/\n/\r/\0/
\x00-\x1F/\x7F pass → log/header injection + SSRF obfuscation). Windows
inconsistency (:38 `^[A-Za-z]:\\` vs :52 `^[A-Za-z]:[\\/]` → C:/... local but not
playable).
Medium: case-sensitive scheme (:30-31; HTTP:// / leading-space rejected vs RFC
case-insensitive → normalize strip+lower). no type guard (:22-24; None/bytes →
AttributeError → isinstance). blocklist-only sensitive paths (:26-28,:38-40;
bypassed by file:///etc sans slash, %65ncoding, %2e%2e, /proc/self/environ variants,
C:/Windows sans exact, UNC \\?\ , /data/data sans slash, /root/, ~/.ssh/, /private/;
no unquote+normpath). empty file:///content:// (:26-28 no path-present check).
bare / and //evil share True (:38 over-permissive).
Low: credentials silently accepted (user:pass@, user@evil — valid but phishing);
magic 4096 (const + comment); private name but app-level use (publicize).
Fix: normalize (isinstance, strip, empty/len/dirty-char reject, s != raw reject);
network (lower prefix + urlparse hostname non-empty + netloc space check + userinfo
log/reject); local (unquote+normpath+lower before blocklist + missing entries +
slashless variants + traversal + non-empty path); regex `^[A-Za-z]:[\\/]` shared
helper; 4096 + sensitive list → constants. Shape given in audit.

## utils.py (21) — Needs Fixes (happy-path ASCII OK).

Medium: non-ASCII alpha passes (ÉA/ÄÖ → isalpha True → chr() outside Regional
Indicator U+1F1E6-FF → bogus non-flag). No type guard (None/int → AttributeError/
TypeError; flag None partially handled, 0/12/list not).
Low: no strip (" US"/"us\n" → ""); manual escape duplicates stdlib (order & first
currently correct, fragile).
Correct: escape output matches html.escape(quote=True); offset 127397 = 1F1E6-65
correct; upper() handles case; invalid ASCII length/nonalpha → "" correct.
Fix: ASCII A-Z guard post-upper (isascii / range); isinstance guards (or coerce/
raise); strip+upper before len; stdlib html.escape; named offset const + __all__.
