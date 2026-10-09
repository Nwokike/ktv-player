# 22 — App Audit: Components (14 files)

## channel_card.py (108) — Needs Fixes. Zero Flet API misuse (all props verified).

Medium: M1 nested focusable-in-focusable (star IconButton inside card FilledButton
:50-68 in :88-107) — 2 D-pad stops per channel, inner star no focus ring. Move star
to sibling overlay (Stack) or add explicit focused style + accept 2-stop. M2 cached
logo path may not be valid Image.src (:31-35): storage/ path is not an asset path;
needs runtime check per target (bytes/base64 or under assets if not rendering);
also double-fetch (Image direct + grid background download) + no rebuild when cache
lands. M3 None bypasses .get defaults (:27-28 url/name → Text(None)/ValueKey(None)/
on_play(None) crash on null playlist data) → `or ""`/`or "Unknown"` + logo
isinstance guard (line 29 already `or`). M4 duplicate ValueKey("") (:90) + "" in
favorites set → unique fallback key, skip key when falsy.
Low: docstring micro-zoom false (attach_focus_pop no-op); helper clobbers
on_focus/blur; status dot no tooltip/semantics; static Favorite tooltip; error icon
no color; from flet import Control style; border_radius int checked-OK.
Correctness: image logic right (TTL/evict/"/icon.png" handling verified); no
placeholder/gapless/fade (harsh pop + scroll flash); focus border/overlay correct,
star focus default (M1); favorite icon/color + lambda captures safe (own binding,
no loop bug); inner-gesture-wins assumed (needs on-device confirm).
Fixes: resolve M2 per-target first; M3/M4 one-liners; Stack star; gapless_playback +
placeholder + semantics; refresh-on-download notify; delete-or-realize zoom.

## channel_grid.py (231) — Bugs Found.

High: H1 dots grey on pages ≥2 (:20-35,:60-78): grid never subscribes; parent only
tracks visible[:24] == page 0 slice; page 1+ results arrive, nobody re-renders.
Grid-owned set_on_change → local version bump (or lift pagination up). H2 mid-grid
ad branch dead (:89-113; AD_ROW_INTERVAL 24 == PAGE_SIZE 24 → `0+24<24` never true;
docstring false). Set interval < page size w/ expand=False, or delete branch/param/
docstring. H3 new ad per render (:115-122; fresh AdService+BannerAd incl. 500ms
ticks → request storm/flicker). use_memo/hoist + page-as-prop.
Medium: M1 page clamp desyncs state (:53-54 local rebind, no setter) → use_effect +
setter (never set during render). M2 stale seeding on same-length swaps (:78 deps
lack content identity) → dep on URL tuple/channels_hash. M3 no scroll-to-top
(:161-165,:199-203) → scroll controller. M4 double drain/seed race w/ home_screen →
single owner. M5 pagination Containers unfocusable, no disabled semantics
(:130-204; guarded lambda only) → real buttons + focus. M6 latent crash if ad branch
fires (expand=True in scrollable Column → Flutter assertion) → expand=False.
Low: dead layout constants; spacer fallback; untyped ad_service + hasattr; per-render
imports; ValueKey("") dup; context.page raises (inject page).
Checked NOT bugs: col lowercase keys valid; Padding positional (l,t,r,b) correct;
icons present; scroll/AUTO, Border.all, Container ink/click, component/hooks/context
all correct; hook order stable; cache access single-loop safe.

## empty_state.py (54) — Needs Fixes. No API misuse (all verified).

Medium: M1 fixed width=300 (:34) overflows <340px / narrow on wide → max_width/
constraint + max_lines. M2 silent button suppression (:37 `if label and handler`) →
raise on half-wiring or disabled button.
Low: bare Callable → ControlEventHandler; icon no muted color; verbose
Alignment(0,0) → CENTER; title unconstrained vs message; no container padding;
from flet import Control → ft.Control.
Layout/icon/button construction all correct.

## filter_bar.py (370) — Bugs Found. No hard API misuse.

High: H1 country pill is_selected wrong (:166 `!= _default_country` vs "all";
fresh load "all" != "Global" → True → selected look with no filter; category/custom
use correct idle predicates). Fix: `!= "all"`. H2 Fav (:308-334) + "+" (:345-359)
Containers unfocusable (verified: no autofocus/focus/on_focus on Container/
PopupMenuButton/Control) → OutlinedButton/Chip/TextButton. H3 no focus management
at all (no autofocus, no focus ring, Row scroll won't follow focus).
Medium: M1 custom_playlists hint lies (`list[str]|None` but dict handled :247-250)
→ `list[str]|dict[str,int]|None`. M2 "Cancel" resets/applies (country→default/all,
category→all, custom→none) instead of dismiss → rename All/Reset + checked= state.
M3 _compact one-shot snapshot (:94-100; no resize subscription; None/0 → compact) →
caller prop via on_resized/LayoutBuilder. M4 hit target ~22-24px < 48dp → vertical
8-10. M5 total_count dead (:84; passed len(visible), never read) → remove or badge.
Low: Fav ignores _compact; on_add_content drops event (breaks def handler(e));
doc drift (Fav OutlinedButton/+ IconButton vs actual Containers); case-sensitive
sort; "+" Text vs Icons.ADD + no tooltip/semantics; positional Padding fragile.
Chips/dropdowns/fav logic correct (captures, copies, guards, dict/list branches,
resets); focus/D-pad FAIL (zero autofocus/ring, row won't follow).

## focus_styles.py (94) — Needs Fixes. card_button_style correct; pop ships no-op.

Medium: M1 attach_focus_pop (:52-91) admitted dead, still wired into 2 cards →
delete or implement. M2 frozen rationale overgeneralizes: _frozen set only on
@component Renderer path; repo mounts imperatively (zero @component in src), so
_frozen never set and scale+update would NOT raise — docstring "verified" claim
holds only for declarative path. M3 missing PRESSED (overlay/side only
FOCUSED/HOVERED/DEFAULT → pressed falls back TRANSPARENT; focused border flashes
to 1px on press). M4 no animate_scale → even success snaps, not pops.
Low: bare except hides RuntimeError/ValueError; handler overwrite; shared mutable
Padding default; unvalidated overlay_alpha/scale; wrong radius annotation;
deferred imports; bgcolor/color scalar (DISABLED identical to enabled).
Verified: ControlState keys/dict form, RoundedRectangleBorder scalar radius,
BorderSide(width,color), with_opacity order/range, scalar style props, Button
on_focus/blur, scale type, frozen error strings (accurate for @component trees).
Fix: decide pop (delete or animate_scale impl + chained handlers + logged errors);
add PRESSED (+DISABLED/SELECTED); None-sentinel padding; hoisted imports; fixed
annotations; corrected docstring.

## folder_expansion_tile.py (112) — Bugs Found.

High: H1 GridView(expand=True) in Column in ListView (:78-93 in :108-111; parent
local_screen:437-446): scrollable viewport, no shrinkWrap, flex in unbounded
parent → collapse/throw/competing scroll (TV remote bad). Replace inner grid with
ResponsiveRow/Wrap under outer ListView, or explicit height from row count. H2
col={...} on grid children dead (:80-82; parent GridView not ResponsiveRow).
Medium: M1 runs_count=3 + max_extent=160 both set (:85-86; Flutter uses one) →
pick one. M2 stale-closure setters (:30-36) → functional updaters. M3 no child keys
(:69-77) → key=v.path (parent passes key=f.path correctly). M4 title/count
divergence (:38-43 folder.count vs len) → use total both. M5 empty-folder expanded
renders empty grid, no placeholder.
Low: untyped Callables → Callable[[LocalVideo],None]; from flet import Control
style; int padding → Padding.all; cards rebuilt per count (fine ≤48); parent
fresh lambdas per tile per render.
Checked: expansion reset-on-expand correct; ListTile on_click + icon swap correct;
key handling at call site correct (component decorator pops key); liveliness
re-slice flows if new object (in-place mutation risk noted); OutlinedButton
content valid.

## header.py (202) — Needs Fixes. No invalid API (all 7 icons verified).

Medium: context.page getattr-false-safe (:47-48,:52,:163 — property raises
RuntimeError, getattr default can't help) → try/except. Dead _current_theme state
(:47 never read; icon recomputed from AppColors._is_dark) → tick or consume.
Stale update chip (:61-63 reads plain core_state attrs, no subscription) → lift to
props/parent rebuild. Overflow risk (:195-201 Row SPACE_BETWEEN + actions Row, no
wrap/scroll/expand; version text + 5 buttons clip narrow) → spacer/expand/
breakpoint collapse. Asset /icon.svg (:183; no top-level assets/; depends on
assets_dir; leading-slash semantics differ; no error_content) → confirm assets_dir,
no-slash, fallback + semantics. 
Low: inverted theme affordance (icon=current vs action); positional Padding(10,4..)
→ symmetric; Image color without SRC_IN (tint washes art; consider icon_white);
brand_row single-child Row → Container; private AppColors._is_dark cross-module →
public is_dark; zero-arg callback assumption (async breaks); double update on
toggle (toggle_theme already updates + set_state rebuild); ink Container not a11y
button (no focus/disabled/semantics).
Layout/search/refresh/fav/add/version/theme wrappers correct as triggers; no
debounce/loading/disabled on refresh (concurrent refresh risk).

## loading_state.py (53) — Needs Fixes (minor). Zero API misuse.

Medium: M1 fixed _SKELETON_WIDTH 360 (:17,:28) overflows <380px viewports → max_width/
responsive. M2 label color 24% ON_SURFACE (:46) unreadable → ON_SURFACE_VARIANT.
Low: redundant centering (outer Container centers; inner Column CENTER no-op w/o
height); inner Column horizontal default START (add CENTER); subtle shimmer delta
(0.10→0.24, widen if weak); unconditional expand=True hostile nested → param;
"" treated as missing (None-check if empty-label allowed).
Shimmer correct (base+highlight, period 1400, infinite loop, theme-adaptive token).

## offline_flow.py (49) — Pass. Zero API misuse (all runtime-verified).

Low: untyped callbacks (parent passes async (e) — compatible, but contract
undocumented); verbose Alignment(0,0) → CENTER; no autofocus/disabled on Retry
(TV + double-submit); hardcoded English (rest uses LBL_*); no padding/width
constraint (phone/overscan); grey_dim fallback safe (verified).
Wiring correct (parent owns is_loading/is_offline; mount probe → loading → offline/
online; retry clears + re-probes; skip persists Other+terms + on_complete);
stateless view correct. Limits parent-side: empty-success reads as offline, no
timeout/backoff/listener, no failure detail (no message prop).
Polish: autofocus Retry, disabled/busy prop (+ProgressRing), message prop,
LBL_* strings, padding + max_width, typed signature, Card styling, semantics.

## recently_watched.py (130) — Bugs Found.

High: H1 on_play arity lie (:24 `Callable[[str],None]` vs :58 call 2-arg) —
works only because home handler takes (url,title=None); any standard 1-arg callback
(TypeError on tap). Fix type + standardize all to (url,title=None). H2 legacy-string
dead branch (:34 entry.get before isinstance; :44-48 unreachable; history list[dict]
claims dicts) → isinstance-first or delete branch.
Medium: M1 "View all" Container unfocusable (:97-109; verified no focus API) →
IconButton/FilledButton + focus-ring + autofocus policy. M2 logo miss never enqueues
(:50-54; no enqueue_logo_download unlike channel_grid) → miss-path enqueue once
per URL + scheme check (startswith("/") conflates asset/POSIX/cached). M3 empty-url
entries render "Stream" + on_play("",None) → skip falsy. M4 build_controls_on_demand
on ≤10 list (:123; default already True; no item_extent; D-pad focus anomalies) →
False here, keep for full screen.
Low: height 90 clips card+ring (→108; add rail padding); _display_name leaks
query/fragment + trailing-/Stream fallback (unquote/strip/domain); positional
Padding → symmetric; redundant spacer + SPACE_BETWEEN; import os in fn + history
None guard; 30px hit target (→48 on button conversion); no keys (key=url).
Horizontal ListView recipe correct (props exist); logo read path correct, miss path
bug; cards focusable w/ ring (no autofocus policy); pop correctly unused.

## version_dialog.py (205) — Needs Fixes. Happy path sound.

Medium: M1 web popup-blocker (:27-37,:40-46,:77-98): click → pop → run_task →
launch_url outside gesture → likely blocked. Use ft.OpenUrl actions or in-gesture
launch. M2 UrlLauncher per-click in background task (implicit context; show_dialog
correct but registration fragile; notify via context.page can mistarget) → bind
once on page thread or declarative OpenUrl. M3 wrong error string (ERR_NETWORK
playback message for link failure) → dedicated ERR_OPEN_LINK. M4 blind pop_dialog
(:40-46,:49-57; pops topmost; check dismisses whatever opened meanwhile) →
track instance. M5 no duplicate guard (fresh AlertDialog per call → double-tap
stacks; show_dialog raises only for same instance) → open-instance tracking.
M6 dead window during re-check (:49-66,:109-115; pop then 4s network, no UI) →
keep open + ProgressRing + disable Check. M7 mandatory not modal vs back
(modal= blocks outside-tap only; no on_dismiss guard) → re-show/block + audit
system back.
Low: dead try/except around pop_dialog (never raises); run_task lambda style +
parallel-check double-click; stale update_available/data on None re-check; fixed
width=360 → page clamp; no URL validation before launch (launch_url(None) risk);
lambda captures correct (checked).
Dialog lifecycle/UrlLauncher/platform/Markdown/contracts all valid (props, enums,
icons, Markdown value/selectable/extensions/on_tap_link, notes_for string,
check_for_update dict|None). Platform: ANDROID check null-safe; ANDROID_TV
distinct — TV falls to GitHub-only (add TV explicitly if APK path supported);
iOS/mac/win/linux GitHub-only correct; store/APK links should use
EXTERNAL_APPLICATION.

## video_card.py (109) — Bugs Found. No Flet API misuse.

High: H1 stale thumbnails, fallback never upgrades (:29-37,:82): Icon-vs-Image
branch at build; video_thumbnails mutates model post-build + page.update can't swap
Icon→Image. New frames appear only on rebuild/rescan. → @component + state/effect,
rebuild after prewarm, or always-Image w/ placeholder+error_content. H2 nested
clickable double-fire (:51-100 FilledButton > IconButton; comment asserts inner
wins, no stopPropagation in Flet) → tapping Options may also start playback.
Restructure (Container/GestureDetector card + sibling menu in Stack/Row) or verify
w/ tap logging + regression test.
Medium: M1 fixed height=140 overflow (:53; content ~150-160 w/ padding+2-line name+
scale) + mismatched grid aspect (0.75/160 → ~200 cell vs 140 button dead space).
M2 D-pad bloat (2 stops/video; inner no focus style; pop no-op) → single stop +
styled inner or order. M3 no keys (card + caller :69-77) → key=video.path. M4 image
height-only (:31-37) → constrain width/fill.
Low: _format_size dup (local_scanner handles <0; import once); generic tooltip +
no semantics; radius 10 vs 16 + icon/image size jump; lambda capture styles unify.
Wiring: thumbnail API right, refresh broken; duration field never populated
(model dead — surface badge or drop); menu gating + long-press valid (TV D-pad
long-press gap mitigated by visible button); focus wiring valid (border/overlay
only); playback (path)→play_stream(url,title=None) + validator absolute/file/
content — correct.

## add_custom_content_dialog.py (178) — Bugs Found. use_dialog pattern correct.

High: cooldown dead (:60-64 + :83-84): _reset set_last_add(0.0) wipes timestamp
just set; component stays mounted (home:373 always mounts, open toggles) so
ADD_CONTENT_COOLDOWN 5.0 never enforced. Remove from _reset; set after reset.
on_dismiss arity (:156 `lambda: on_close()`; DialogControl.on_dismiss takes event)
→ `lambda e: on_close()`.
Medium: fire-and-forget on_added (:86-88; _handle_add async yet create_task(result)
→ swallowed exceptions + outlived dialog) → await + try/log. stale double-submit
guard (:67-69 reads render-time is_adding) → use_ref in-flight flag (storage safe
via lock, but duplicate on_added refresh). modal-stack fragile (:163-171;
has_pushed as use_state + [open]-only deps; unmount before render leaks stack) →
use_ref + unmount cleanup / direct close_modal in paths. hardcoded "Playlist"
(:73; name ignored in playlist mode; manager dedupes by URL so all share name) →
expose name or derive from URL. bare except + notify, no log (:89-90).
weak _is_valid_url (:26-31; prefix tuple + len>7 accepts http://x/spaces/garbage;
redundant uppercase) → urlparse/strip/space-reject/.m3u hint.
Low: has_pushed declared after use_dialog (works, rules-of-hooks hygiene → top);
e.control.selected[0] assumes non-empty (set flags explicitly + e.data + guard);
url_field no max_length/autofocus/error_text (name has 200); async _handle_cancel
no await → sync; _notify aliases after use → top; url_field.focus correct only via
use_dialog frozen-diff (acceptable).
Save flow order mostly right; consider on_added before on_close (or awaited) so
failing refresh surfaces before clear. Improvements list in audit (cooldown order,
await on_added, ref guards, validation, autofocus/max_length, playlist naming,
logging, e.data).
