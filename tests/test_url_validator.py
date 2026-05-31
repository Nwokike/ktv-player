"""Tests for the URL validator in main.py."""

import sys
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def validator():
    from src.main import _is_valid_play_url

    return _is_valid_play_url


class TestUrlValidator:
    def test_valid_http(self, validator):
        assert validator("http://example.com/stream.m3u8") is True

    def test_valid_https(self, validator):
        assert validator("https://example.com/stream.m3u8") is True

    def test_valid_rtsp(self, validator):
        assert validator("rtsp://example.com/stream") is True

    def test_valid_rtmp(self, validator):
        assert validator("rtmp://example.com/live") is True

    def test_valid_rtp(self, validator):
        assert validator("rtp://example.com:5000") is True

    def test_valid_mms(self, validator):
        assert validator("mms://example.com/stream") is True

    def test_empty_string(self, validator):
        assert validator("") is False

    def test_too_long(self, validator):
        assert validator("http://" + "a" * 4090) is False

    def test_file_scheme_blocked_etc(self, validator):
        assert validator("file:///etc/passwd") is False

    def test_file_scheme_blocked_proc(self, validator):
        assert validator("file:///proc/self/environ") is False

    def test_file_scheme_blocked_windows(self, validator):
        assert validator("file:///C:/Windows/system32") is False

    def test_file_scheme_safe(self, validator):
        assert validator("file:///sdcard/Movies/video.mp4") is True

    def test_content_scheme(self, validator):
        assert validator("content://media/video/file.mp4") is True

    def test_windows_path_safe(self, validator):
        assert validator("D:\\Videos\\movie.mp4") is True

    def test_windows_path_blocked(self, validator):
        assert validator("C:\\Windows\\system32") is False

    def test_unix_path_safe(self, validator):
        assert validator("/home/user/video.mp4") is True

    def test_unix_path_blocked(self, validator):
        assert validator("/etc/passwd") is False

    def test_random_text(self, validator):
        assert validator("not-a-url") is False

    def test_none_value(self, validator):
        assert validator(None) is False
