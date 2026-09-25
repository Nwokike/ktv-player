"""Long-press delete on local videos (MX-Player style)."""

import inspect
from types import SimpleNamespace

import flet as ft

from components.video_card import VideoCard
from screens import local_screen
from services.local_scanner import LocalVideo


def _video():
    return LocalVideo(name="a.mp4", path="/videos/a.mp4", size=10)


def test_card_wraps_gesture_detector_when_long_press_given():
    hit = []
    v = _video()
    card = VideoCard(video=v, on_play=lambda p: None, on_long_press=hit.append)
    assert isinstance(card, ft.GestureDetector)
    card.on_long_press(SimpleNamespace())
    assert hit == [v]


def test_card_stays_plain_button_without_long_press():
    card = VideoCard(video=_video(), on_play=lambda p: None)
    assert isinstance(card, ft.FilledButton)


def test_delete_flow_uses_mediastore_then_rescans(tmp_path):
    """Delete goes through MediaStore (the scanner's source of truth) with a
    file fallback, then rescans."""
    src = inspect.getsource(local_screen.LocalScreen)
    assert "async def _delete_video" in src
    assert "delete_media_store_video" in src
    assert "delete_media_store_video, v.content_uri" in src
    assert "delete_local_file" in src
    assert "await _scan()" in src


def test_delete_local_file_removes_and_reports(tmp_path):
    from services.local_scanner import delete_local_file

    f = _make_file(tmp_path, "a.mp4")
    assert delete_local_file(str(f)) is True
    assert not f.exists()
    # Already-gone file counts as deleted (no false failure).
    assert delete_local_file(str(f)) is True
    assert delete_local_file("") is False


def test_delete_media_store_video_off_android_returns_false():
    from services.local_scanner import delete_media_store_video

    # No JVM off-Android — must degrade to False (caller shows the
    # "Android may block deleting" warning) rather than crash.
    assert delete_media_store_video("") is False
    assert delete_media_store_video("content://media/external/video/media/1") is False


def test_local_video_has_content_uri_field():
    v = LocalVideo(name="a.mp4", path="/a.mp4")
    assert v.content_uri == ""


def _make_file(tmp_path, name):
    p = tmp_path / name
    p.write_bytes(b"x")
    return p


def test_local_screen_wires_long_press_to_folder_tiles():
    src = inspect.getsource(local_screen.LocalScreen)
    assert "on_long_press_video=_on_video_long_press" in src
    assert "on_video_menu=" in src
    assert "async def _video_menu" in src
    assert "show_dialog" in src


def test_windows_defaults_are_merged_with_storage_paths(monkeypatch):
    r"""StoragePaths must never replace the desktop defaults.

    On Windows `StoragePaths` answers with Downloads only, so the old
    `if paths: return paths` short-circuit skipped `get_default_scan_paths()`
    — the only place C:\Users\<who>\Videos is listed. A machine with 1354
    videos there scanned as "0 folders".
    """
    import asyncio

    from screens import local_screen

    class _FakeStoragePaths:
        async def get_downloads_directory(self):
            return "C:/Users/me/Downloads"

        async def get_external_storage_directory(self):
            return None

        async def get_external_storage_directories(self):
            return []

    import flet

    monkeypatch.setattr(flet, "StoragePaths", _FakeStoragePaths, raising=False)
    monkeypatch.setattr(
        local_screen,
        "get_default_scan_paths",
        lambda: [
            "C:/Users/me/Videos",
            "C:/Users/me/Downloads",
            "C:/Users/me/Desktop",
        ],
    )
    paths = asyncio.run(local_screen._get_storage_paths())

    assert "C:/Users/me/Videos" in paths, "Videos library was skipped"
    assert "C:/Users/me/Desktop" in paths
    # No duplicates from the merge.
    assert len(paths) == len(set(paths))
