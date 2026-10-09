"""Android Picture-in-Picture via pyjnius (API 26+).

All Android classes are resolved through the shared android_bridge at call
time and every entry point is best-effort: on desktop (no JVM) or
unsupported devices these functions return False / 0 without raising.

Threading: activity.* invocations (enterPictureInPictureMode,
setPictureInPictureParams, finish) are UI-thread-affiliated — call them on
the main looper (or a Flet method channel), NOT via blind asyncio.to_thread
(which risks CalledFromWrongThreadException). Pure reflection (autoclass,
SDK_INT, hasSystemFeature) is safe off-thread.

Needs-hardware-confirm: the MainActivity field names below are
mock-verified only. If PiP is silently dead on the target APK, dump the
MainActivity fields via adb and extend android_bridge._ACTIVITY_ATTRS.

Verified facts:
- enterPictureInPictureMode(PictureInPictureParams) and
  PictureInPictureParams.Builder: API 26+.
- Builder.setAutoEnterEnabled(bool): API 31+ (Android 12) — the system then
  enters PiP automatically when the user swipes home.
- Aspect ratio bounds: 2.39:1 .. 1:2.39 (floats 2.39 .. 0.41841).
- Manifest requirement (applied by CI): android:supportsPictureInPicture.
"""

import logging
import threading
from fractions import Fraction

from services.android_bridge import (
    PIP_FEATURE,
    autoclass_cached,
    get_activity,
    invalidate_activity_cache,
    sdk_int,
)

logger = logging.getLogger(__name__)

_MIN_API = 26
_AUTO_ENTER_API = 31
_ASPECT_MIN = 0.41841  # 1:2.39
_ASPECT_MAX = 2.39

# One-shot warning: Android 16 rejects auto-PiP on some devices and the
# pyjnius exception string is a full Java stacktrace.
_auto_pip_warned = False
_warn_lock = threading.Lock()


def api_level() -> int:
    """Android SDK_INT, or 0 when not runnable (desktop/older stacks)."""
    return sdk_int()


def is_pip_supported() -> bool:
    try:
        if sdk_int() < _MIN_API:
            return False
        activity = get_activity()
        if activity is None:
            return False
        pm = activity.getPackageManager()
        return bool(pm.hasSystemFeature(PIP_FEATURE))
    except Exception as ex:
        logger.debug("PiP feature check failed: %s", ex)
        return False


def _clamp_aspect(aspect: float) -> float:
    return min(_ASPECT_MAX, max(_ASPECT_MIN, float(aspect)))


def _build_params(auto_enter: bool, aspect: float | None):
    builder = autoclass_cached("android.app.PictureInPictureParams$Builder")()
    sdk = sdk_int()
    if sdk >= _AUTO_ENTER_API:
        # Explicit both ways. Skipping the setter when disabling left the
        # previously-set auto-enter params active, so the app kept entering
        # PiP on minimize long after the player closed.
        builder.setAutoEnterEnabled(auto_enter)
    elif auto_enter:
        logger.debug("auto_enter requested below API 31 — dropped (no setter)")
    if aspect is not None:
        if aspect <= 0:
            raise ValueError(f"aspect must be positive, got {aspect!r}")
        clamped = _clamp_aspect(aspect)
        # Fraction from ints (not float): Fraction(16/9) bakes in the binary
        # float error before limiting; numerator/denominator pairs are exact.
        ratio = Fraction(int(clamped * 1000), 1000).limit_denominator(239)
        builder.setAspectRatio(
            autoclass_cached("android.util.Rational")(
                ratio.numerator, ratio.denominator
            )
        )
    return builder.build()


def enter_pip(aspect: float | None = None) -> bool:
    """Enter Picture-in-Picture now. Returns the system's own verdict.

    NOTE: calling this disables future auto-enter on the Activity (the
    params built here carry auto_enter=False) — that is intentional and
    callers that want auto-enter afterwards must re-arm via set_auto_pip.
    Call on the main thread (see module docstring).
    """
    if not is_pip_supported():
        return False
    activity = get_activity()
    if activity is None:
        return False
    try:
        effective_aspect = aspect if aspect is not None else 16 / 9
        return bool(
            activity.enterPictureInPictureMode(
                _build_params(auto_enter=False, aspect=effective_aspect)
            )
        )
    except Exception as ex:
        logger.warning("enter_pip failed: %s", ex)
        return False


def set_auto_pip(enabled: bool, aspect: float | None = None) -> bool:
    """Android 12+: system auto-enters PiP when the user swipes home.

    Returns False below API 31 (unsupported — the player falls back to a
    lifecycle hook). Callers MUST distinguish this from True: the old
    no-op-True made unsupported look armed.
    Call on the main thread (see module docstring).
    """
    if sdk_int() < _AUTO_ENTER_API:
        return False
    activity = get_activity()
    if activity is None:
        return False
    try:
        activity.setPictureInPictureParams(
            _build_params(
                auto_enter=enabled, aspect=aspect if aspect is not None else 16 / 9
            )
        )
        return True
    except Exception as ex:
        global _auto_pip_warned
        # str(ex) can be empty (a Java throwable with no message), and
        # splitlines() then returns [] — indexing it would raise inside
        # the except block.
        first_line = (str(ex).splitlines() or [""])[0]
        with _warn_lock:
            warned = _auto_pip_warned
            _auto_pip_warned = True
        if not warned:
            logger.warning(
                "set_auto_pip failed (further failures logged at debug): %s",
                first_line,
            )
        else:
            logger.debug("set_auto_pip failed: %s", first_line)
        return False


def exit_app() -> bool:
    """Finish the Android activity, returning the user to the calling app.
    Flet's window.close() is a desktop-only no-op on Android (its Dart
    closeWindow() guards isDesktopPlatform()), so closing a deep-linked
    video requires finishing the activity directly.
    Call on the main thread (see module docstring)."""
    activity = get_activity()
    if activity is None:
        return False
    try:
        activity.finish()
        invalidate_activity_cache()
        return True
    except Exception as ex:
        logger.warning("exit_app failed: %s", ex)
        return False
