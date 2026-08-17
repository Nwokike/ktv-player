"""Android Picture-in-Picture via pyjnius (API 26+).

All Android classes are resolved through jnius at call time and every entry
point is best-effort: on desktop (no JVM) or unsupported devices these
functions return False / 0 without raising. Heavy jnius reflection is meant
to be called via ``asyncio.to_thread`` — same pattern as the screenshot
MediaScanner code.

Verified facts:
- enterPictureInPictureMode(PictureInPictureParams) and
  PictureInPictureParams.Builder: API 26+.
- Builder.setAutoEnterEnabled(bool): API 31+ (Android 12) — the system then
  enters PiP automatically when the user swipes home.
- Aspect ratio bounds: 2.39:1 .. 1:2.39 (floats 2.39 .. 0.41841).
- Manifest requirement (applied by CI): android:supportsPictureInPicture.
"""

import logging
from fractions import Fraction

logger = logging.getLogger(__name__)

_MIN_API = 26
_AUTO_ENTER_API = 31
_ASPECT_MIN = 0.41841  # 1:2.39
_ASPECT_MAX = 2.39

_activity = None


def _get_activity():
    global _activity
    if _activity is not None:
        return _activity
    import os

    try:
        from jnius import autoclass
    except Exception:
        return None

    for cls_name in (
        os.getenv("MAIN_ACTIVITY_HOST_CLASS_NAME"),
        "ng.kiri.ktvplayer.MainActivity",
        "net.flet.MainActivity",
        "com.flet.flet_android.MainActivity",
        "org.kivy.android.PythonActivity",
    ):
        if not cls_name:
            continue
        try:
            host = autoclass(cls_name)
            activity = getattr(host, "mActivity", None) or getattr(
                host, "mCurrentActivity", None
            )
            if activity:
                _activity = activity
                return activity
        except Exception as ex:
            logger.debug("PiP activity candidate %s unavailable: %s", cls_name, ex)
    return None


def api_level() -> int:
    """Android SDK_INT, or 0 when not runnable (desktop/older stacks)."""
    try:
        from jnius import autoclass

        return int(autoclass("android.os.Build$VERSION").SDK_INT)
    except Exception:
        return 0


def is_pip_supported() -> bool:
    try:
        if api_level() < _MIN_API:
            return False
        activity = _get_activity()
        if activity is None:
            return False
        pm = activity.getPackageManager()
        return bool(pm.hasSystemFeature("android.software.picture_in_picture"))
    except Exception as ex:
        logger.debug("PiP feature check failed: %s", ex)
        return False


def _clamp_aspect(aspect: float) -> float:
    return min(_ASPECT_MAX, max(_ASPECT_MIN, float(aspect)))


def _build_params(auto_enter: bool, aspect: float | None):
    from jnius import autoclass

    builder = autoclass("android.app.PictureInPictureParams$Builder")()
    sdk = api_level()
    if auto_enter and sdk >= _AUTO_ENTER_API:
        builder.setAutoEnterEnabled(True)
    if aspect:
        ratio = Fraction(_clamp_aspect(aspect)).limit_denominator(1000)
        builder.setAspectRatio(
            autoclass("android.util.Rational")(ratio.numerator, ratio.denominator)
        )
    return builder.build()


def enter_pip(aspect: float | None = None) -> bool:
    """Enter Picture-in-Picture now. Returns True when the call was made."""
    if not is_pip_supported():
        return False
    activity = _get_activity()
    if activity is None:
        return False
    try:
        effective_aspect = aspect if aspect else 16 / 9
        activity.enterPictureInPictureMode(
            _build_params(auto_enter=False, aspect=effective_aspect)
        )
        return True
    except Exception as ex:
        logger.warning("enter_pip failed: %s", ex)
        return False


def set_auto_pip(enabled: bool, aspect: float | None = None) -> bool:
    """Android 12+: system auto-enters PiP when the user swipes home.

    No-op (True) below API 31 — the player falls back to a lifecycle hook.
    """
    if api_level() < _AUTO_ENTER_API:
        return True
    activity = _get_activity()
    if activity is None:
        return False
    try:
        activity.setPictureInPictureParams(
            _build_params(auto_enter=enabled, aspect=aspect or 16 / 9)
        )
        return True
    except Exception as ex:
        logger.warning("set_auto_pip failed: %s", ex)
        return False
