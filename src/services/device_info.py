"""Best-effort device summary for diagnostics (Settings → Development).

Used in the log-terminal header so TV issues can be diagnosed from a pasted
clipboard dump: model, Android version/API, leanback (TV) detection and app
version. Off-JVM (desktop) falls back to platform info; never raises.
"""

import logging
import platform as _platform

from core.constants import APP_BUILD_NUMBER, APP_VERSION
from services.tv_detect import is_tv_device

logger = logging.getLogger(__name__)

_logged_unavailable = False


def get_device_summary() -> str:
    """Multi-line device/app summary (safe on every platform)."""
    lines = [f"OS: {_platform.system()} {_platform.release()} ({_platform.machine()})"]
    try:
        from services.android_bridge import autoclass_cached

        Build = autoclass_cached("android.os.Build")
        version = autoclass_cached("android.os.Build$VERSION")
        manufacturer = getattr(Build, "MANUFACTURER", None) or "unknown"
        model = getattr(Build, "MODEL", None) or "unknown"
        release = getattr(version, "RELEASE", None) or "unknown"
        try:
            sdk = int(version.SDK_INT)
        except Exception:
            sdk = "unknown"
        # Per-field fallbacks: one bad getter must not drop the whole line.
        lines.insert(
            0,
            f"Device: {manufacturer} {model} - Android {release} (SDK {sdk})",
        )
    except Exception:
        # Expected on every desktop call (no JVM): log once WITHOUT a
        # traceback. The old exc_info=True polluted the very log dump being
        # diagnosed, on every refresh.
        global _logged_unavailable
        if not _logged_unavailable:
            _logged_unavailable = True
            logger.debug("Android device info unavailable (not Android/JVM)")
    try:
        lines.append(f"Android TV (leanback): {is_tv_device()}")
    except Exception:
        logger.debug("TV detection unavailable", exc_info=True)
    lines.append(f"App: {APP_VERSION} (build {APP_BUILD_NUMBER})")
    return "\n".join(lines)
