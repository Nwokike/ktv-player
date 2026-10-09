"""Shared Android bridge: one place for activity/SDK/reflection helpers.

pip_service, tv_detect, local_scanner and immersive_player each copy-pasted
the same MainActivity hunt + SDK_INT read + autoclass call. That quadrupled
the places where a stale cached activity, a frozen env read, or a missed
attribute could silently kill PiP / TV detection / MediaStore / screenshots
on device. Everything lazily imports jnius inside functions (desktop has no
JVM — `import jnius` raises there), so this module imports cleanly anywhere.

Needs-hardware-confirm: activity field names (mActivity/mCurrentActivity)
and the ActivityThread fallback are mock-verified only. If PiP or TV detect
is silently dead on the target APK, dump the MainActivity fields via adb
and extend _ACTIVITY_ATTRS / _HOST_CANDIDATES.
"""

import logging
import os
import threading

logger = logging.getLogger(__name__)

LEANBACK_FEATURE = "android.software.leanback"
PIP_FEATURE = "android.software.picture_in_picture"

_lock = threading.Lock()
_activity = None
_sdk_int: int | None = None
_class_cache: dict[str, object] = {}
_tv_cache: bool | None = None
_tv_cache_time: float = 0.0
_TV_UNKNOWN_TTL = 5.0


def _host_candidates() -> tuple[str | None, ...]:
    # Read INSIDE the resolver (not import-frozen): tests and late env setup
    # can set MAIN_ACTIVITY_HOST_CLASS_NAME after import.
    return (
        os.getenv("MAIN_ACTIVITY_HOST_CLASS_NAME"),
        "ng.kiri.ktvplayer.MainActivity",
        "net.flet.MainActivity",
        "com.flet.flet_android.MainActivity",
        "org.kivy.android.PythonActivity",
    )


_ACTIVITY_ATTRS = ("mActivity", "mCurrentActivity")


def autoclass_cached(name: str):
    """autoclass with a process-level cache: the first hit pays the full
    hierarchy walk, repeats are free. Main-thread reflection jank happens
    once instead of per call."""
    cached = _class_cache.get(name)
    if cached is not None:
        return cached
    from jnius import autoclass

    cls = autoclass(name)
    _class_cache[name] = cls
    return cls


def sdk_int() -> int:
    """Android SDK_INT, memoized (never changes per process). 0 off-device."""
    global _sdk_int
    if _sdk_int is not None:
        return _sdk_int
    try:
        version = autoclass_cached("android.os.Build$VERSION")
        _sdk_int = int(version.SDK_INT)
    except Exception:
        _sdk_int = 0
    return _sdk_int


def get_activity(refresh: bool = False):
    """The current Android Activity, or None off-device / unreachable.

    Cached, but revalidated: isFinishing()/isDestroyed() activities are
    dropped and re-resolved (rotation, PiP return, TV mode change recreate
    the activity — the old write-once global served a dead one forever).
    """
    global _activity
    with _lock:
        if _activity is not None and not refresh:
            try:
                if _activity.isFinishing():
                    _activity = None
                else:
                    try:
                        if _activity.isDestroyed():
                            _activity = None
                    except Exception:
                        pass
            except Exception:
                _activity = None
            if _activity is not None:
                return _activity
        activity = _resolve_activity_locked()
        _activity = activity
        return activity


def _resolve_activity_locked():
    try:
        from jnius import autoclass
    except Exception:
        return None
    for cls_name in _host_candidates():
        if not cls_name:
            continue
        try:
            host = autoclass(cls_name)
        except Exception:
            logger.debug("Android bridge: no host class %s", cls_name)
            continue
        # Probe each attribute INDEPENDENTLY: the old `getattr(a) or
        # getattr(b)` skipped the second attr whenever the first getattr
        # RAISED (missing field), instead of merely being empty.
        activity = None
        for attr in _ACTIVITY_ATTRS:
            try:
                candidate = getattr(host, attr, None)
            except Exception as ex:
                logger.debug("Activity attr %s missing on %s: %s", attr, cls_name, ex)
                continue
            if candidate is not None:
                activity = candidate
                break
        if activity is not None:
            return activity
    return None


def invalidate_activity_cache() -> None:
    """Drop the cached activity (call after finish()/recreate)."""
    global _activity
    with _lock:
        _activity = None


def _reset_for_tests() -> None:
    """Clear all bridge caches (tests only)."""
    global _activity, _sdk_int, _tv_cache, _tv_cache_time
    with _lock:
        _activity = None
        _sdk_int = None
        _class_cache.clear()
        _tv_cache = None
        _tv_cache_time = 0.0


def is_tv_device() -> bool:
    """True only on leanback declarers. Verdicts cached; unknown retried
    (with a 5s TTL so desktop+jnius-but-no-activity doesn't spin forever);
    desktop/no-JVM is a definitive False."""
    import time

    global _tv_cache, _tv_cache_time
    with _lock:
        if _tv_cache is not None:
            return _tv_cache
        if time.time() - _tv_cache_time < _TV_UNKNOWN_TTL and _tv_cache_time:
            return False
    detected = _detect_tv()
    with _lock:
        if detected is not None:
            _tv_cache = detected
        else:
            _tv_cache_time = time.time()
    return bool(detected)


def _detect_tv() -> bool | None:
    """True/False verdict, or None when detection could not run at all
    (no activity reachable yet — caller retries later)."""
    try:
        from jnius import autoclass  # noqa: F401 (presence probe)
    except ImportError:
        return False
    except Exception:
        return False
    activity = get_activity()
    if activity is None:
        return None
    try:
        pm = activity.getPackageManager()
        return bool(pm.hasSystemFeature(LEANBACK_FEATURE))
    except Exception:
        logger.debug("TV leanback probe failed", exc_info=True)
        return None
