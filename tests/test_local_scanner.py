"""Tests for the local video scanner."""

from pathlib import Path


from src.services.local_scanner import (
    _format_size,
    _has_nomedia,
    _is_video_file,
    get_default_scan_paths,
    is_mobile,
)


class TestIsVideoFile:
    def test_mp4(self):
        assert _is_video_file(Path("video.mp4")) is True

    def test_mkv(self):
        assert _is_video_file(Path("video.mkv")) is True

    def test_avi(self):
        assert _is_video_file(Path("video.avi")) is True

    def test_txt_not_video(self):
        assert _is_video_file(Path("readme.txt")) is False

    def test_no_extension(self):
        assert _is_video_file(Path("Makefile")) is False

    def test_uppercase_extension(self):
        assert _is_video_file(Path("video.MP4")) is True

    def test_mixed_case(self):
        assert _is_video_file(Path("video.MkV")) is True


class TestHasNomedia:
    def test_nomedia_exists(self, tmp_path):
        (tmp_path / ".nomedia").write_text("")
        assert _has_nomedia(tmp_path) is True

    def test_nomedia_not_exists(self, tmp_path):
        assert _has_nomedia(tmp_path) is False

    def test_nested_nomedia(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / ".nomedia").write_text("")
        assert _has_nomedia(sub) is True
        assert _has_nomedia(tmp_path) is False


class TestFormatSize:
    def test_zero_bytes(self):
        assert _format_size(0) == "0 B"

    def test_negative_bytes(self):
        assert _format_size(-1) == "0 B"

    def test_bytes(self):
        assert "500 B" in _format_size(500)

    def test_kilobytes(self):
        result = _format_size(1500)
        assert "KB" in result

    def test_megabytes(self):
        result = _format_size(2_500_000)
        assert "MB" in result

    def test_gigabytes(self):
        result = _format_size(3_500_000_000)
        assert "GB" in result

    def test_exact_1kb(self):
        result = _format_size(1024)
        assert "KB" in result


class TestIsMobile:
    def test_on_windows(self):
        import os

        if os.name == "nt":
            assert is_mobile() is False


class TestGetDefaultScanPaths:
    def test_returns_list(self):
        paths = get_default_scan_paths()
        assert isinstance(paths, list)
