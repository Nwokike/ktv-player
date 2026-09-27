"""UI sound effects are a designed no-op off Android.

Desktop is deliberately silent (no winsound, owner's call), and CI runs
where jnius cannot initialize must never see an exception escape.
"""

from utils.sfx import play_click


def test_play_click_never_raises_without_android():
    play_click()  # must return silently on any non-Android host
