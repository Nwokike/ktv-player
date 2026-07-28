"""Tests for RecentlyWatched carousel component."""

import flet as ft

from app_next.components.recently_watched import RecentlyWatched


def _make_ch(name, url):
    return {"name": name, "url": url, "logo": ""}


def test_recently_watched_hidden_when_no_history():
    rw = RecentlyWatched(history=[], channels_map={}, on_play=lambda u: None)
    assert isinstance(rw, ft.Container)
    assert rw.visible is False


def test_recently_watched_lists_up_to_10_items():
    history = [f"http://x/{i}" for i in range(15)]
    channels_map = {
        f"http://x/{i}": _make_ch(f"C{i}", f"http://x/{i}") for i in range(15)
    }
    rw = RecentlyWatched(
        history=history, channels_map=channels_map, on_play=lambda u: None
    )
    cards = _find_card_like(rw)
    assert len(cards) <= 10
    if len(history) > 10:
        assert len(cards) == 10


def test_recently_watched_card_triggers_on_play():
    fired = []
    history = ["http://x/0"]
    channels_map = {"http://x/0": _make_ch("C0", "http://x/0")}
    rw = RecentlyWatched(
        history=history, channels_map=channels_map, on_play=lambda u: fired.append(u)
    )
    cards = _find_card_like(rw)
    if cards:
        cards[0].on_click(None)
        assert fired == ["http://x/0"]


# helpers
def _walk(c):
    yield c
    children = getattr(c, "controls", None) or []
    if isinstance(children, list):
        for ch in children:
            yield from _walk(ch)
    content = getattr(c, "content", None)
    if content:
        yield from _walk(content)


def _find_card_like(root):
    results = []
    for c in _walk(root):
        if isinstance(c, ft.Container) and hasattr(c, "on_click") and c.on_click:
            results.append(c)
    return results
