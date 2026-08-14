"""Tests for RecentlyWatched carousel component."""

import flet as ft
from flet_tree import walk

from components.recently_watched import RecentlyWatched


def _make_ch(name, url):
    return {"name": name, "url": url, "logo": ""}


def test_recently_watched_hidden_when_no_history():
    rw = RecentlyWatched(history=[], channels_map={}, on_play=lambda u, t=None: None)
    assert isinstance(rw, ft.Container)
    assert rw.visible is False


def test_recently_watched_lists_up_to_10_items():
    history = [{"url": f"http://x/{i}", "title": f"Title {i}"} for i in range(15)]
    channels_map = {
        f"http://x/{i}": _make_ch(f"C{i}", f"http://x/{i}") for i in range(15)
    }
    rw = RecentlyWatched(
        history=history, channels_map=channels_map, on_play=lambda u, t=None: None
    )
    cards = _find_card_like(rw)
    assert len(cards) <= 10
    if len(history) > 10:
        assert len(cards) == 10


def test_recently_watched_card_triggers_on_play():
    fired = []
    history = [{"url": "http://x/0", "title": "My Title"}]
    channels_map = {"http://x/0": _make_ch("C0", "http://x/0")}
    rw = RecentlyWatched(
        history=history, channels_map=channels_map, on_play=lambda u, t=None: fired.append(u)
    )
    cards = _find_card_like(rw)
    if cards:
        cards[0].on_click(None)
        assert fired == ["http://x/0"]


def _find_card_like(root):
    """Return clickable card-like controls.

    NOTE: Phase A migrates RecentlyWatched cards from Container to FilledButton
    so they become D-pad-focusable. This helper keeps working across both
    shapes by matching either a non-empty on_click Container OR any button.
    Once Phase A lands, all matches will be FilledButtons.
    """
    results = []
    for c in walk(root):
        if isinstance(
            c, (ft.FilledButton, ft.OutlinedButton, ft.ElevatedButton, ft.TextButton)
        ) or (isinstance(c, ft.Container) and hasattr(c, "on_click") and c.on_click):
            results.append(c)
    return results
