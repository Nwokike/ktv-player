"""Tests for the URL validator in main.py."""

import pytest


@pytest.fixture
def validator():
    from src.main import _is_valid_play_url

    return _is_valid_play_url


class TestUrlValidator:
    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com/stream.m3u8",
            "https://example.com/stream.m3u8",
            "rtsp://example.com/stream",
            "rtmp://example.com/live",
            "rtp://example.com:5000",
            "mms://example.com/stream",
            "file:///sdcard/Movies/video.mp4",
            "content://media/video/file.mp4",
            "D:\\Videos\\movie.mp4",
            "/home/user/video.mp4",
        ],
    )
    def test_valid_urls(self, validator, url):
        assert validator(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            "",
            "http://" + "a" * 4090,
            "file:///etc/passwd",
            "file:///proc/self/environ",
            "file:///C:/Windows/system32",
            "C:\\Windows\\system32",
            "/etc/passwd",
        ],
    )
    def test_blocked_urls(self, validator, url):
        assert validator(url) is False

    def test_random_text(self, validator):
        assert validator("not-a-url") is False

    def test_none_value(self, validator):
        assert validator(None) is False


class TestIsLocalMediaUrl:
    def test_unix_path(self):
        from core.url_validator import is_local_media_url

        assert is_local_media_url("/home/user/video.mp4") is True

    def test_file_scheme(self):
        from core.url_validator import is_local_media_url

        assert is_local_media_url("file:///sdcard/Movies/video.mp4") is True

    def test_content_scheme(self):
        from core.url_validator import is_local_media_url

        assert is_local_media_url("content://media/video/file.mp4") is True

    def test_windows_drive(self):
        from core.url_validator import is_local_media_url

        assert is_local_media_url("D:\\Videos\\movie.mp4") is True

    def test_http_stream_is_not_local(self):
        from core.url_validator import is_local_media_url

        assert is_local_media_url("https://example.com/stream.m3u8") is False

    def test_rtsp_stream_is_not_local(self):
        from core.url_validator import is_local_media_url

        assert is_local_media_url("rtsp://example.com/live") is False

    def test_empty(self):
        from core.url_validator import is_local_media_url

        assert is_local_media_url("") is False


class TestPhase4ValidatorHardening:
    @pytest.fixture
    def validator(self):
        from src.main import _is_valid_play_url

        return _is_valid_play_url

    def test_bare_scheme_rejected(self, validator):
        assert validator("http://") is False
        assert validator("https:///") is False

    def test_uppercase_scheme_accepted(self, validator):
        assert validator("HTTP://example.com/x.m3u8") is True
        assert validator("HTtP://example.com/x.m3u8") is True

    def test_whitespace_rejected(self, validator):
        assert validator(" https://example.com/x.m3u8") is False
        assert validator("https://example.com/x.m3u8\n") is False
        assert validator("https://example.com/a b.m3u8") is False

    def test_credentials_rejected(self, validator):
        assert validator("http://user:pass@example.com/x.m3u8") is False
        assert validator("http://example.com@evil.com/x.m3u8") is False

    def test_encoded_traversal_rejected(self, validator):
        assert validator("file:///%2e%2e/etc/passwd") is False
        assert validator("file:///etc") is False
        assert validator("file://") is False

    def test_forward_slash_windows_drive(self, validator):
        assert validator("C:/Videos/movie.mp4") is True

    def test_non_string_rejected(self, validator):
        assert validator(123) is False
        assert validator(b"http://example.com/x") is False


class TestPhase4DeeplinkGates:
    def _route(self, **params):
        import base64 as _b64
        import urllib.parse as _up

        def _e(s):
            return _b64.urlsafe_b64encode(s.encode()).decode().rstrip("=")

        q = "&".join(f"{k}={_up.quote(_e(v))}" for k, v in params.items())
        return f"ktv://play?{q}"

    def test_wrong_scheme_rejected(self):
        from core.deeplink import parse_deep_link

        assert parse_deep_link("https://evil.com/?url=eA") == (None, None, None, None)

    def test_file_url_rejected_from_external_link(self):
        import base64 as _b64

        from core.deeplink import parse_deep_link

        enc = _b64.urlsafe_b64encode(b"file:///sdcard/a.mp4").decode().rstrip("=")
        assert parse_deep_link(f"ktv://play?url={enc}") == (None, None, None, None)

    def test_blocked_header_dropped_others_kept(self):
        import json as _j

        from core.deeplink import parse_deep_link

        url = "https://example.com/s.m3u8"
        hdrs = {"Authorization": "secret", "X-Ok": "yes"}
        route = self._route(
            url=url,
            referer="https://example.com/",
            headers=_j.dumps(hdrs),
        )
        u, _t, _r, h = parse_deep_link(route)
        assert u == url
        assert h == {"X-Ok": "yes"}

    def test_oversize_field_rejected(self):
        from core.deeplink import parse_deep_link

        route = f"ktv://play?url={'A' * 9000}"
        assert parse_deep_link(route) == (None, None, None, None)

    def test_plaintext_title_not_misdecoded(self):
        import base64 as _b64

        from core.deeplink import parse_deep_link

        url = "https://example.com/s.m3u8"
        enc = _b64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
        # "abcd" is valid base64 alphabet but must stay plaintext.
        out = parse_deep_link(f"ktv://play?url={enc}&title=abcd")
        assert out[1] == "abcd"
