"""Local-video thumbnail cache (MX-Player style, Android-only extraction)."""

import os
from types import SimpleNamespace

import flet as ft
import pytest

from components.video_card import VideoCard
from services import video_thumbnails
from services.local_scanner import LocalVideo


@pytest.fixture(autouse=True)
def _tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(video_thumbnails, "THUMBNAIL_CACHE_DIR", str(tmp_path))
    return tmp_path


def _video(path="/videos/a.mp4", size=1234, modified=1700000000.0, content_uri=""):
    return LocalVideo(
        name="a.mp4", path=path, size=size, modified=modified, content_uri=content_uri
    )


def test_thumbnail_path_is_deterministic():
    v = _video()
    assert video_thumbnails.thumbnail_path(v) == video_thumbnails.thumbnail_path(
        _video()
    )


def test_thumbnail_path_changes_with_content():
    base = video_thumbnails.thumbnail_path(_video())
    assert video_thumbnails.thumbnail_path(_video(modified=1700000001.0)) != base
    assert video_thumbnails.thumbnail_path(_video(size=9999)) != base


def test_get_cached_thumbnail_miss_then_hit(_tmp_cache):
    v = _video()
    assert video_thumbnails.get_cached_thumbnail(v) is None
    path = video_thumbnails.thumbnail_path(v)
    with open(path, "wb") as f:
        f.write(b"\xff\xd8\xffstub")
    assert video_thumbnails.get_cached_thumbnail(v) == path


@pytest.mark.asyncio
async def test_extract_thumbnail_noop_off_android(monkeypatch):
    # No jnius on desktop: extraction returns None and writes nothing.
    v = _video()
    assert await video_thumbnails.extract_thumbnail(v) is None
    assert not os.path.exists(video_thumbnails.thumbnail_path(v))


@pytest.mark.asyncio
async def test_extract_thumbnail_writes_frame(monkeypatch, _tmp_cache):
    v = _video(content_uri="content://media/external/video/media/42")
    written = {}

    def _fake_extract(video_path, out_path, content_uri=""):
        written["src"] = video_path
        written["uri"] = content_uri
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"\xff\xd8\xffframe")
        return True

    monkeypatch.setattr(video_thumbnails, "_extract_sync", _fake_extract)
    path = await video_thumbnails.extract_thumbnail(v)
    assert path == video_thumbnails.thumbnail_path(v)
    assert written["src"] == v.path
    # MediaStore rows carry a content:// handle — preferred over the raw
    # path under scoped storage.
    assert written["uri"] == v.content_uri
    # Second call is a pure cache hit (extraction not repeated).
    monkeypatch.setattr(
        video_thumbnails,
        "_extract_sync",
        lambda *_: pytest.fail("should not re-extract cached thumbnail"),
    )
    assert await video_thumbnails.extract_thumbnail(v) == path


@pytest.mark.asyncio
async def test_prewarm_fills_videos_and_updates_page(monkeypatch, _tmp_cache):
    videos = [
        _video(path=f"/videos/{i}.mp4", modified=1700000000.0 + i) for i in range(3)
    ]

    def _fake_extract(video_path, out_path, content_uri=""):
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"\xff\xd8\xffframe")
        return True

    monkeypatch.setattr(video_thumbnails, "_extract_sync", _fake_extract)
    page = SimpleNamespace(update_calls=0)
    page.update = lambda: setattr(page, "update_calls", page.update_calls + 1)

    filled = await video_thumbnails.prewarm_thumbnails(videos, page)

    assert filled == 3
    assert all(v.thumbnail for v in videos)
    assert page.update_calls == 1


def test_video_card_shows_image_when_thumbnail_exists():
    v = _video()
    v.thumbnail = "/tmp/thumb.jpg"
    card = VideoCard(video=v, on_play=lambda p: None)
    images = _walk(card)
    assert any(isinstance(c, ft.Image) and c.src == "/tmp/thumb.jpg" for c in images)


def test_video_card_falls_back_to_icon_without_thumbnail():
    v = _video()
    card = VideoCard(video=v, on_play=lambda p: None)
    images = _walk(card)
    assert not any(isinstance(c, ft.Image) for c in images)
    assert any(isinstance(c, ft.Icon) for c in images)


def _walk(c, seen=None):
    if seen is None:
        seen = []
    if c is None or id(c) in seen:
        return seen
    seen.append(c)
    seen.append(id(c))
    for attr in ("content", "controls", "error_content"):
        child = getattr(c, attr, None)
        if isinstance(child, (list, tuple)):
            for ch in child:
                _walk(ch, seen)
        else:
            _walk(child, seen)
    return seen
