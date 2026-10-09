# 13 — flet-permission-handler 1.0.1 Deep Dive

Version: 1.0.1 (`Requires-Python >=3.10`, requires flet==1.0.1). App declares >=0.86.5.
Thin wrapper: 3 async methods, no events, no rationale API.

## API (installed source)

`PermissionHandler(ft.Service)`:
- `get_status(permission) -> Optional[PermissionStatus]`
- `request(permission) -> Optional[PermissionStatus]`
- `open_app_settings() -> bool`
Platform guard: ANDROID, ANDROID_TV, IOS, WINDOWS, Web only.

PermissionStatus (6): GRANTED, DENIED, PERMANENTLY_DENIED, LIMITED (iOS14+/Android14+
partial), PROVISIONAL (iOS notifications), RESTRICTED (iOS parental/MDM).

Permission (39): ACCESS_MEDIA_LOCATION, ACCESS_NOTIFICATION_POLICY,
ACTIVITY_RECOGNITION, APP_TRACKING_TRANSPARENCY, ASSISTANT, AUDIO (Android13+),
BACKGROUND_REFRESH, BLUETOOTH*, CALENDAR_*, CAMERA, CONTACTS, CRITICAL_ALERTS,
IGNORE_BATTERY_OPTIMIZATIONS, LOCATION*, MANAGE_EXTERNAL_STORAGE (Android11+),
MEDIA_LIBRARY (iOS), MICROPHONE, NEARBY_WIFI_DEVICES, NOTIFICATION, PHONE, PHOTOS,
PHOTOS_ADD_ONLY, REMINDERS, REQUEST_INSTALL_PACKAGES, SCHEDULE_EXACT_ALARM,
SENSORS*, SMS, SPEECH, STORAGE (deprecated 13+, always denied — use VIDEOS/AUDIO/
PHOTOS), SYSTEM_ALERT_WINDOW, UNKNOWN (return-only), VIDEOS (Android13+).

Missing vs Dart: no requestMultiple, no shouldShowRequestRationale/checkServiceStatus,
no status stream. Rationale must be hand-built with AlertDialog. get/request return
None on native failure — must null-check.

## Current usage (single integration point)

`services/permission_service.py:request_storage_permission` ← called fire-and-forget
from local_screen (_on_mount, _pick_folder_async).

Good: granular VIDEOS→STORAGE pair matches manifest (READ_MEDIA_VIDEO,
READ_MEDIA_VISUAL_USER_SELECTED, READ/WRITE_EXTERNAL_STORAGE, legacy flag);
ANDROID_TV + IOS gated, desktop/web bypassed; lazy singleton via page.services;
returns False (not True) when ungranted.

Gaps: never calls get_status/open_app_settings; never branches DENIED vs
PERMANENTLY_DENIED vs LIMITED vs RESTRICTED vs None; local_screen ignores the bool
and scans anyway; no rationale/settings dialog (LBL_GRANT_PERMISSION unused);
requests VIDEOS even on API<33 and iOS instead of SDK branching; not registered at
boot (race with first request); NOTIFICATION correctly unused (in-app notices are
SnackBar) but undocumented.

## Opportunities

1. Check-before-request: get_status on mount; request only if DENIED/None.
2. Permanent-denial path: PERMANENTLY_DENIED → dialog with LBL_GRANT_PERMISSION →
   open_app_settings (Android11+: denied twice = no-op re-request).
3. Android14+ partial: manifest already has VISUAL_USER_SELECTED; treat LIMITED as
   usable + "Select more videos" re-request expands picker.
4. Hand-rolled rationale AlertDialog before first request + post-denial settings route.
5. SDK-aware branching via device_info/jnius SDK_INT: ≥33 VIDEOS only; <33 STORAGE
   only; iOS PHOTOS. Removes guaranteed-failing first prompt.
6. Wire the bool in local_screen: False → EmptyState with Grant-Permission action.
7. Boot registration next to FilePicker/Connectivity.
8. Other permissions correctly unused: AUDIO/PHOTOS (video scanner only),
   MANAGE_EXTERNAL_STORAGE (avoid Play burden), NOTIFICATION (only if system
   notifications added), REQUEST_INSTALL_PACKAGES (only if update_service sideloads —
   currently missing from manifest), ACCESS_MEDIA_LOCATION (only if EXIF needed).

## Edge cases

- STORAGE on 13+ always denied by design — SDK branching removes log noise.
- MANAGE_EXTERNAL_STORAGE needs dedicated Settings intent — don't adopt casually.
- Deletion consent (MediaStore polling) is separate from runtime permissions.
- Desktop tests: before_update throws off-mobile; mock get_status/request in pytest.
