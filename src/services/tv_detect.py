"""Android TV / Google TV detection via pyjnius (leanback feature).

Best-effort and cached: returns True only on devices that declare
``android.software.leanback`` (Android TV / Google TV). Phones, tablets
and desktop (no JVM) return False. Uses the same jnius activity
resolution policy as :mod:`services.pip_service`; the reflection runs at
most once per process.
"""

import logging
import os

logger = logging.getLogger(__name__)

_ACTIVITY_CANDIDATES = (
    os.getenv("MAIN_ACTIVITY_HOST_CLASS_NAME"),
    "ng.kiri.ktvplayer.MainActivity",
    "net.flet.MainActivity",
    "com.flet.flet_android.MainActivity",
    "org.kivy.android.PythonActivity",
)

_tv_cache: bool | None = None


def is_tv_device() -> bool:
    """True on Android TV / Google TV, False everywhere else."""
    global _tv_cache
    if _tv_cache is not None:
        return _tv_cache
    detected = _detect()
    # A False produced because no activity was reachable yet is NOT a
    # verdict — caching it would pin the app to "phone" for the whole
    # session and let TV ads through.
    if detected is not None:
        _tv_cache = detected
    return bool(detected)


def _detect() -> bool | None:
    """True/False, or None when detection could not run at all."""
    try:
        from jnius import autoclass
    except Exception:
        return False
    for cls_name in _ACTIVITY_CANDIDATES:
        if not cls_name:
            continue
        try:
            host = autoclass(cls_name)
            activity = getattr(host, "mActivity", None) or getattr(
                host, "mCurrentActivity", None
            )
            if not activity:
                continue
            result = bool(
                activity.getPackageManager().hasSystemFeature(
                    "android.software.leanback"
                )
            )
            logger.info("TV detection: leanback=%s (via %s)", result, cls_name)
            return result
        except Exception as ex:
            logger.debug("TV detection: %s unavailable: %s", cls_name, ex)
    return None
