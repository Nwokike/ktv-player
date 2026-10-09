"""UI sound effects are a designed no-op off Android.

Desktop is deliberately silent (no winsound, owner's call), and CI runs
where jnius cannot initialize must never see an exception escape.
"""

from utils.sfx import play_click


def test_play_click_never_raises_without_android():
    play_click()  # must return silently on any non-Android host


def test_sfx_singleton_reused():
    """Module singleton: repeated taps share one generator (no churn)."""
    from utils import sfx

    assert sfx._generator is None  # off-Android: nothing allocated
    play_click()
    play_click()
    assert sfx._generator is None  # still nothing (no JVM)


def test_sfx_release_safe_when_empty():
    from utils.sfx import release

    release()  # must not raise with nothing allocated
