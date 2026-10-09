# 31 — Consolidated Ship-Blockers (High severity, file:line)

No code changed. Ads items are REPORT ONLY (need explicit go).

## Player + entry (20)

- main.py:166-174 lifecycle e.data hidden dead → e.state HIDE/PAUSE/DETACH save.
- main.py:770-781 fallback omits /blank → mirror ktv:// underlay.
- main.py:512-519 play dedupe serializes-not-drops → init locks + playing flag.
- app_shell.py:164-165 toggle_favorite(state,url) swapped → (url,state).
- app_shell.py:159-162 create_task play → run_task.
- immersive_player.py:631-640 PiP single is_playing check → arm on ready/tick/load.
- immersive_player.py:693-722 periodic save defined, never called → call in _on_pos.
- immersive_player.py:315-316 bg pause+resume vs PiP → pause False while armed, resume False.
- controls.py:177 favorite maybe-unawaited → verify, run_task if coro.
- ad_service.py:27 annotation crash w/o flet_ads; :290 vs :204 consent bypass in
  fallback; :303/:374-377 leak + True-before-show; :59+ is_mobile() unverified.

## Channels + history + favorites (21/22/25)

- provider.py:215-219 refresh returns [] instead of awaiting lock; :210-212 no tier
  tag (premium serves free list); app_loader.py:66-68 force offline wipes grid.
- app_loader.py:74-87 mutates DB dicts (is_custom leak); :150 empty overwrites good.
- m3u_parser.py:42-47 missing-URL eats next entry; :51 drops rtmps/rtsps/srt/mms/
  uppercase; :20 quoted-comma name misparse.
- normalize.py:90-93 tvg-id shadow (hd suppresses us → Global).
- recently_watched_screen.py:26 legacy str crashes list; :118-132 AppBar-in-Column
  no back; :85 on_play arity untyped.
- recently_watched.py:24 vs :58 arity lie (1-arg type, 2-arg call).
- home_screen.py:298-316 views.append leak; :198 callback never unregistered;
  :322-331 banner per render/tick.
- channel_grid.py:20-35/H1 pages 2+ dots grey; :89-113 dead ad branch; :115-122 ad
  per render.
- favorites.py:33-37 no-loop silent drop; :17-19 deferred guard no-debounce;
  :21-27 snapshot overwrite lost update.
- database/manager.py:59 bak never tried on corruption; :53-54 empty = clean empty;
  :69-72/:103+ unvalidated legacy str/int crash; :94-95 failed save marked clean.
- core/state.py:1,9,12-14 field() w/o dataclass (works by accident).
- controller_ctx.py:63 pop_modal zero-arg vs real (self,name).
- use_autofocus.py:24 ft.MutableRef missing → import-time AttributeError.
- notifications.py:75-85 SnackBar overlay.append bypass (leak per toast); :69-87 no
  queue.
- liveliness.py:42-44 clear() never notifies; :35 _dirty unbounded dupes.

## Network + proxy + liveliness (24/14)

- http_client.py:23-27 global close unowned; :8-20 init race.
- hls_proxy.py:137 verify=False global; :599-612 502 Unknown wire; :297-307 bad
  b64/JSON hangs (no response).
- iptv_service.py:24 catch-all + [] (cancels + error identity lost); :21-23
  unbounded resp.text.
- liveliness_checker.py:123-125 offline→False (paints red); :145-156 PoolTimeout
  cached dead; :137-150 non-streaming Range GET (full-file OOM); :28 per-instance
  semaphore (no global throttle).
- logo_cache.py loop-bound queue + no queued-dedup + worker-path no evict (detailed
  in 24).
- deeplink.py:57-76 headers unsanitized; :26-30 file/content from external link.
- url_validator.py:30-36 network branch no-op (no hostname); :23/:33 whitespace/
  control pass; :38 vs :52 Windows slash inconsistency.
- update_service.py:66-68 announcement branch dead (docstring vs gate).
- kiri_license.py:286-293 revoke memory-only (boot re-unlocks); :159-180 rejected
  not cleared; :42-43 untyped error (watcher polls hard 400s); :305 non-string token
  crash.
- local_scanner.py:285 exists-filter kills scoped storage; :268-276 _data + list
  projection fails on 10+; :240-249 SAF primary-only.
- youtube_resolver.py:166-168 reverse-arity drop → 403; :328 page regex dead;
  :311-325 jsUrl escaped → fetch fail; n-param missing (throttle); :74-76 swap div0.
- video_thumbnails.py:41+ model AttributeError aborts batch; :46-57 unbounded cache.

## Device + misc

- pip_service.py:122-125 ignores enter() bool (always True); :28 dead activity cached;
  :45-58 MainActivity fields likely wrong (silent PiP death).
- video_card.py:29-37 Icon/Image branch can't upgrade (new thumbs never appear);
  :51-100 nested clickable double-fire risk.
- folder_expansion_tile.py:78-93 GridView(expand) in Column in ListView (unbounded).
- filter_bar.py:166 country pill wrong predicate; :308-359 Fav/+ unfocusable.
- search_screen.py:39-62 listener clobber; :404 unguarded page; :64-80 scan orphans;
  :277-279 local path → stream handler mismatch.
- local_screen.py:163-166 background failure wipes folders; :145+ scan stampede;
  :158-179 prewarm leak.
- settings_screen.py:265+ create_task ×8; :443-449 country save no error path;
  :670+ launcher no feedback; :979-982 license None deref.
- onboarding_screen.py:34+ persist unguarded (half-written first launch); :106+
  double-submit; :76 flash.
- add_custom_content_dialog.py:60-84 cooldown dead (reset wipes timestamp); :156
  on_dismiss arity TypeError.
- changelog.py:52-53 fallback returns oldest (2.0.6) not latest.
- verson_dialog: web popup-blocker (gesture-outside launch), blind pop, dup dialogs.
- crash_reporter.py:45-46 same-second overwrite; :64-67 traceback synthesized.
