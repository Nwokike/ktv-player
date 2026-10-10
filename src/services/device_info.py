"""Best-effort device summary for diagnostics (Settings → Development).

Used in the log-terminal header so TV issues can be diagnosed from a pasted
clipboard dump: model, Android version/API, leanback (TV) detection and app
version. Off-JVM (desktop) falls back to platform info; never raises.
"""

import logging
import platform as _platform

from core.constants import APP_BUILD_NUMBER, APP_VERSION

logger = logging.getLogger(__name__)


def get_device_summary() -> str:
    """Multi-line device/app summary (safe on every platform)."""
    lines = [f"OS: {_platform.system()} {_platform.release()} ({_platform.machine()})"]
    try:
        from jnius import autoclass

        Build = autoclass("android.os.Build")
        lines.insert(
            0,
            f"Device: {Build.MANUFACTURER} {Build.MODEL} — "
            f"Android {Build.VERSION.RELEASE} (SDK {Build.VERSION.SDK_INT})",
        )
    except Exception:
        logger.debug("Android device info unavailable (not Android/JVM)", exc_info=True)
    try:
        from services.tv_detect import is_tv_device

        lines.append(f"Android TV (leanback): {is_tv_device()}")
    except Exception:
        pass
    lines.append(f"App: {APP_VERSION} (build {APP_BUILD_NUMBER})")
    return "\n".join(lines)
