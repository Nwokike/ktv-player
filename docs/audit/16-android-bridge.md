# 16 — pyjnius 1.7.0 Android Bridge Deep Dive

Version: 1.7.0 (`jnius/__init__.py`, METADATA). Declared in
`tool.flet.android.dependencies = ["pyjnius"]` + dev group.
Desktop behavior verified: `import jnius` on Win32 raises
`Exception: Unable to find JAVA_HOME` — all app code lazily imports inside
functions with try/except. Correct pattern, do not "fix".

Native ext present: `jnius.cp314-win_amd64.pyd`.

## APIs (reflect.py + __init__.py)

- `autoclass("android.os.Build")` — full hierarchy walk, constructors, methods,
  fields, bean-getter properties, JavaMultipleMethod overload resolution. Cached in
  MetaJavaClass.get_javaclass — repeat autoclass cheap after first hit.
- `ensureclass(name)` — idempotent warm-up.
- `JavaClass/MetaJavaClass/JavaMethod/JavaStaticMethod/JavaField/JavaStaticField/
  JavaMultipleMethod/find_javaclass/JavaException/get_signature` — manual path +
  `method.signatures()` introspection.
- `PythonJavaClass` + `@java_method("()V")` — implement Java interfaces in Python.
- `jnius.detach()` — auto-installed as threading.Thread.run finally-hook, only when
  ANDROID_ARGUMENT in env (on device). Never call manually.
- `protocol_map` — Python dunders for java.util Collection/List/Map/Iterator,
  Iterable/AutoCloseable/Comparable.
- `signatures.py` — jint/jlong/jboolean/…, JArray(), signature(), with_signature().
- `JavaException` is a normal Python Exception subclass — existing `except Exception`
  blocks catch Java throwables. str(ex) often empty/full stacktrace (pip_service
  already truncates to first line).

Unused in app: PythonJavaClass, java_method, cast, ensureclass, explicit protocol_map,
explicit JavaException.

## Current usage (6 touch-points, all lazy + best-effort)

- tv_detect.py — PackageManager.hasSystemFeature("android.software.leanback").
  Caching correct (caches True/False, not transient None).
- device_info.py — Build.MANUFACTURER/MODEL/VERSION.RELEASE/SDK_INT. Safe.
- pip_service.py — SDK_INT, PictureInPictureParams$Builder (+ setAutoEnterEnabled
  API 31+, Rational clamp 0.41841–2.39), enter/setParams/finish. Best PiP code in repo.
  exit_app works around Flet window.close desktop-only.
- local_scanner.py — MediaStore Video Media EXTERNAL_CONTENT_URI query,
  ContentUris.withAppendedId, ContentResolver.delete, createDeleteRequest
  (correctly on android.provider.MediaStore), media_store_exists re-check.
  Cursor close() in finally correct.
- immersive_player.py — MediaStore Images Media insert with is_pending protocol +
  openOutputStream/write/flush/close, MediaScannerConnection.scanFile fallback.
  Heavy calls correctly offloaded with asyncio.to_thread.
- video_thumbnails.py — MediaMetadataRetriever.setDataSource/getFrameAtTime,
  Bitmap$CompressFormat.JPEG, FileOutputStream, File.renameTo checked, mr.release()
  in finally, bitmap.recycle(). Prefers content-URI, falls back to path. Correct.
- utils/sfx.py — ToneGenerator(STREAM_SYSTEM, 80) + startTone(TONE_PROP_BEEP).
- Correctly NOT via jnius: permission_service (flet_permission_handler),
  deeplink (pure ktv:// parse; Intent delivery is Flet routing).

Duplication: `_android_activity` resolution (env MAIN_ACTIVITY_HOST_CLASS_NAME +
ng.kiri.ktvplayer.MainActivity / net.flet.MainActivity / com.flet.flet_android.
MainActivity / org.kivy.android.PythonActivity via mActivity/mCurrentActivity)
copy-pasted in pip_service, tv_detect, local_scanner, immersive_player.

## Opportunities (by value for TV/mobile player)

1. Centralize activity + SDK helpers → one `services/android_bridge.py` with cached
   get_activity(), sdk_int(), get_class(name) cache. Removes 4-way duplication.
2. Keep-screen-on at window level: `activity.getWindow().addFlags(0x80)`
   (FLAG_KEEP_SCREEN_ON). flet_video wakelock covers playback; menus/grids can
   still dim on TV. Clear on pause. WAKE_LOCK already declared.
3. Audio focus: no AudioManager.requestAudioFocus/AUDIOFOCUS_GAIN handling today.
   Assistant/notifications duck over playback. Request on start_playback, abandon
   on close. Also consider STREAM_MUSIC vs STREAM_SYSTEM in sfx (system commonly
   muted on TV).
4. Stronger TV detection: keep leanback primary, add UiModeManager.
   getCurrentModeType()==4 (UI_MODE_TYPE_TELEVISION) + hasSystemFeature touchscreen
   ==False logging. All via already-used autoclass.
5. Network awareness for HLS: ConnectivityManager.getActiveNetwork +
   NetworkCapabilities (NOT_METERED, TRANSPORT_WIFI) to pick initial variant/proxy
   bitrate. Read-only, ACCESS_NETWORK_STATE already declared.
6. Storage volumes: StorageManager.getStorageVolumes instead of hardcoded
   /storage/emulated/0 fallbacks in local_scanner + screenshot fallback.
7. Immersive window flags: setSystemUiVisibility (legacy) / WindowInsetsController
   (API 30+) sticky-immersive + setStatusBar/NavigationBarColor black.
8. Display info: DisplayManager/Display.getRefreshRate + DisplayMetrics (DPI) appended
   to device_info.get_device_summary. Free TV frame-rate diagnostic value.
9. Battery-aware prewarm throttle: BatteryManager CAPACITY/isCharging to shrink
   thumbnails _PREWARM_LIMIT (40) + _EXTRACT_CONCURRENCY (2) when low + unplugged.
10. Cold-start Intent extras: activity.getIntent().getAction/getDataString via jnius
    as fallback if Flet deep-link delivery ever misses. No change while Flet works.

NOT recommended: PARTIAL_WAKE_LOCK for audio-only (Flet wakelock suffices), Vibrator
(TVs lack it), MediaSession lockscreen (Flet owns surface; high cost, low return).

## Crash risks / threading

No ship-blockers. Hardening:
- Stale cached activity: pip_service._activity process-global, never invalidated.
  After recreate (rotation, PiP return, TV mode change) calls hit dead activity,
  throw JavaException (caught, False) but never re-resolve. Fix: drop global or
  re-resolve on JavaException.
- Main-thread reflection jank: is_pip_supported/is_tv_device/play_click/
  get_device_summary run autoclass synchronously; first call walks hierarchy.
  Call once in worker at startup or asyncio.to_thread like PiP/screenshot paths.
- sfx release callback unguarded: loop.call_later + Timer invoke bound Java method
  with no try/except. Wrap release in guard.
- Screenshot API gap: _save_screenshot_android uses relative_path/is_pending
  (API 29+) with no SDK_INT check. Falls through correctly by accident on 26-28 —
  make explicit (if sdk<29: return None).
- _data column deprecated since 29, unreadable under scoped storage for other apps'
  files. Null-filtered + exists-checked so worst case is missed rows. Consider
  DISPLAY_NAME + RELATIVE_PATH + VOLUME_NAME on 29+ with _data legacy fallback.
- Misleading comment (not bug): video_thumbnails except ImportError says "not
  Android" but desktop raises generic Exception("Unable to find JAVA_HOME").
  Outer except Exception still catches — fix comment or catch Exception explicitly.
- scan_android_mediastore runs synchronously incl. exists per row — keep off loop
  (to_thread precedent).
- Do NOT add manual jnius.detach() (hook already handles). Do NOT adopt
  PythonJavaClass callbacks unless needed (scanFile None-None + delete-consent
  poll pattern deliberately avoids activity-result callbacks Flet doesn't expose).
