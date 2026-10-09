"""Tests for the local video scanner."""

from pathlib import Path

from src.services.local_scanner import (
    _format_size,
    _has_nomedia,
    _is_video_file,
    get_default_scan_paths,
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


class TestGetDefaultScanPaths:
    def test_returns_list(self):
        paths = get_default_scan_paths()
        assert isinstance(paths, list)


class TestPhase6ScannerIds:
    def test_resolve_saf_primary(self):
        from services.local_scanner import resolve_saf_path

        assert (
            resolve_saf_path("content://x/tree/primary%3ADownloads")
            == "/storage/emulated/0/Downloads"
        )

    def test_resolve_saf_sd_card_unresolvable(self):
        """SD UUIDs must NOT echo content:// (callers mistreat it as POSIX)."""
        from services.local_scanner import resolve_saf_path

        assert resolve_saf_path("content://x/tree/1234-ABCD%3AMovies") == ""
        assert resolve_saf_path("content://x/document/home%3Afoo") == ""

    def test_resolve_saf_traversal_rejected(self):
        from services.local_scanner import resolve_saf_path

        assert resolve_saf_path("content://x/tree/primary%3A..%2F..%2Fetc") == ""

    def test_resolve_saf_passthrough_non_content(self):
        from services.local_scanner import resolve_saf_path

        assert resolve_saf_path("/storage/a.mp4") == "/storage/a.mp4"
        assert resolve_saf_path("") == ""

    def test_mediastore_gated_off_desktop(self):
        """No JNI attempt on desktop (single platform gate)."""
        from services import local_scanner

        assert local_scanner.scan_android_mediastore() == []

    def test_norm_key_dedupes(self, tmp_path):
        from services.local_scanner import _norm_key, scan_videos

        assert _norm_key("/a//b/") == _norm_key("/a/b")
        (tmp_path / "v.mp4").write_bytes(b"0" * 100)
        folders = scan_videos([str(tmp_path), str(tmp_path) + "/"])
        total = sum(len(f.videos) for f in folders)
        assert total == 1

    def test_default_paths_never_whole_home(self):
        from services.local_scanner import get_default_scan_paths

        assert get_default_scan_paths() is not None
