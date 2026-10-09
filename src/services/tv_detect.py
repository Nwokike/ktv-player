"""Android TV / Google TV detection via pyjnius (leanback feature).

Best-effort and cached: returns True only on devices that declare
``android.software.leanback`` (Android TV / Google TV). Phones, tablets
and desktop (no JVM) return False. Activity resolution, caching and
revalidation live in :mod:`services.android_bridge` — this module is the
leanback question asked over it.
"""

from services.android_bridge import is_tv_device as _bridge_is_tv

__all__ = ["_reset_cache", "is_tv_device"]


def is_tv_device() -> bool:
    """True on Android TV / Google TV, False everywhere else."""
    return _bridge_is_tv()


def _reset_cache() -> None:
    """Clear the cached verdict (tests only)."""
    from services import android_bridge

    android_bridge._reset_for_tests()
