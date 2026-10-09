"""Tests for VideoCard component (sibling menu-button layout)."""

import flet as ft
from flet_tree import walk, walk_texts

from components.video_card import VideoCard
from services.local_scanner import LocalVideo


def _play_surface(card):
    """The FilledButton that starts playback (may sit under GestureDetector
    and/or Stack siblings — never assume the root type)."""
    for c in walk(card):
        if isinstance(c, ft.FilledButton) and callable(getattr(c, "on_click", None)):
            return c
    raise AssertionError("no play surface (FilledButton+on_click) in card")


def _menu_buttons(card):
    return [
        c
        for c in walk(card)
        if isinstance(c, ft.IconButton)
        and c.tooltip
        and c.tooltip.startswith("Options")
    ]


def test_video_card_is_a_focusable_filled_button():
    # Phase A: the PLAY SURFACE is an ft.FilledButton (native D-pad focus on
    # Android TV remotes) — the root is a Container (key + Stack siblings).
    video = LocalVideo(name="test.mp4", path="/path/test.mp4", size=1024)
    card = VideoCard(video=video, on_play=lambda p: None)
    assert _play_surface(card) is not None


def test_video_card_shows_name():
    video = LocalVideo(name="My Movie.mkv", path="/path/movie.mkv", size=2048000)
    card = VideoCard(video=video, on_play=lambda p: None)
    texts = list(walk_texts(card))
    assert any("My Movie" in (t.value or "") for t in texts)


def test_video_card_fires_on_play():
    fired = []
    video = LocalVideo(name="test.mp4", path="/path/test.mp4")
    card = VideoCard(video=video, on_play=lambda p: fired.append(p))
    _play_surface(card).on_click(None)
    assert fired == ["/path/test.mp4"]


def test_menu_button_is_sibling_not_nested():
    """Options must not live inside the play button (double-fire risk)."""
    video = LocalVideo(name="test.mp4", path="/path/test.mp4")
    card = VideoCard(video=video, on_play=lambda p: None, on_menu=lambda v: None)
    surface = _play_surface(card)
    menus = _menu_buttons(card)
    assert len(menus) == 1
    # The menu button is NOT a descendant of the play surface...
    assert all(m not in set(walk(surface)) for m in menus)
    # ...and tapping it does not start playback.
    fired = []
    card2 = VideoCard(
        video=video, on_play=lambda p: fired.append(p), on_menu=lambda v: None
    )
    menus2 = _menu_buttons(card2)
    menus2[0].on_click(None)
    assert fired == []


def test_no_menu_button_without_handler():
    video = LocalVideo(name="test.mp4", path="/path/test.mp4")
    card = VideoCard(video=video, on_play=lambda p: None)
    assert _menu_buttons(card) == []


def test_thumbnail_image_is_always_built():
    """Reactive thumbnail: Image exists even without a cached frame (Icon
    branch at build could never upgrade when prewarm landed)."""
    video = LocalVideo(name="test.mp4", path="/path/test.mp4")
    card = VideoCard(video=video, on_play=lambda p: None)
    images = [c for c in walk(card) if isinstance(c, ft.Image)]
    assert images, "expected an ft.Image with placeholder/error fallback"
