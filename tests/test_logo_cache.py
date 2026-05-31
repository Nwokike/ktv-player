"""Tests for the logo cache service."""



from src.services.logo_cache import (
    _detect_image_type,
    _get_cached_path,
    get_cached_logo,
)


class TestDetectImageType:
    def test_png_signature(self):
        data = b"\x89PNG\r\n\x1a\n" + b"rest of file"
        assert _detect_image_type(data) == "png"

    def test_jpg_signature(self):
        data = b"\xff\xd8\xff\xe0" + b"rest of file"
        assert _detect_image_type(data) == "jpg"

    def test_jpg_short_signature(self):
        data = b"\xff\xd8\xff"
        assert _detect_image_type(data) == "jpg"

    def test_gif87_signature(self):
        data = b"GIF87a" + b"rest"
        assert _detect_image_type(data) == "gif"

    def test_gif89_signature(self):
        data = b"GIF89a" + b"rest"
        assert _detect_image_type(data) == "gif"

    def test_webp_signature(self):
        data = b"RIFFxxxxWEBP"
        assert _detect_image_type(data) == "webp"

    def test_unknown_signature(self):
        data = b"\x00\x00\x00\x00"
        assert _detect_image_type(data) is None

    def test_empty_bytes(self):
        assert _detect_image_type(b"") is None


class TestGetCachedPath:
    def test_returns_string(self):
        path = _get_cached_path("http://example.com/logo.png")
        assert path.endswith(".png")
        assert "storage" in path
        assert "logos" in path

    def test_different_urls_different_paths(self):
        path1 = _get_cached_path("http://example.com/logo1.png")
        path2 = _get_cached_path("http://example.com/logo2.png")
        assert path1 != path2

    def test_same_url_same_path(self):
        path1 = _get_cached_path("http://example.com/logo.png")
        path2 = _get_cached_path("http://example.com/logo.png")
        assert path1 == path2


class TestGetCachedLogo:
    def test_none_for_empty_url(self):
        assert get_cached_logo("") is None

    def test_none_for_icon_png(self):
        assert get_cached_logo("/icon.png") is None

    def test_none_for_nonexistent(self):
        result = get_cached_logo("http://nonexistent.example.com/logo.png")
        assert result is None
