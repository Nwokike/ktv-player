"""Tests for VideoCard component."""

import flet as ft
from flet_tree import walk_texts

from app_next.components.video_card import VideoCard
from services.local_scanner import LocalVideo


def test_video_card_is_a_focusable_filled_button():
    # Phase A: VideoCard is now an ft.FilledButton (not a Container) so the
    # Flet runtime gives it native D-pad focus on Android TV remotes.
    video = LocalVideo(name="test.mp4", path="/path/test.mp4", size=1024)
    card = VideoCard(video=video, on_play=lambda p: None)
    assert isinstance(card, ft.FilledButton)


def test_video_card_shows_name():
    video = LocalVideo(name="My Movie.mkv", path="/path/movie.mkv", size=2048000)
    card = VideoCard(video=video, on_play=lambda p: None)
    texts = list(walk_texts(card))
    assert any("My Movie" in (t.value or "") for t in texts)


def test_video_card_fires_on_play():
    fired = []
    video = LocalVideo(name="test.mp4", path="/path/test.mp4")
    card = VideoCard(video=video, on_play=lambda p: fired.append(p))
    card.on_click(None)
    assert fired == ["/path/test.mp4"]
