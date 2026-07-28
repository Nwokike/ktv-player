"""Tests for VideoCard component."""

import flet as ft

from app_next.components.video_card import VideoCard
from services.local_scanner import LocalVideo


def test_video_card_is_container():
    video = LocalVideo(name="test.mp4", path="/path/test.mp4", size=1024)
    card = VideoCard(video=video, on_play=lambda p: None)
    assert isinstance(card, ft.Container)


def test_video_card_shows_name():
    video = LocalVideo(name="My Movie.mkv", path="/path/movie.mkv", size=2048000)
    card = VideoCard(video=video, on_play=lambda p: None)
    texts = list(_walk_texts(card))
    assert any("My Movie" in (t.value or "") for t in texts)


def test_video_card_fires_on_play():
    fired = []
    video = LocalVideo(name="test.mp4", path="/path/test.mp4")
    card = VideoCard(video=video, on_play=lambda p: fired.append(p))
    card.on_click(None)
    assert fired == ["/path/test.mp4"]


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


def _walk_texts(c):
    for x in _walk(c):
        if isinstance(x, ft.Text):
            yield x
