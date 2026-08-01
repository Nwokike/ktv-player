"""Tests for AddCustomContentDialog pure helpers."""

import time

from components.add_custom_content_dialog import (
    ADD_CONTENT_COOLDOWN,
    _can_add,
    _is_valid_url,
)


def test_valid_url_accepts_http_and_https():
    assert _is_valid_url("http://example.com/stream.m3u8") is True
    assert _is_valid_url("https://example.com/playlist.m3u") is True
    assert _is_valid_url("HTTP://example.com") is True


def test_valid_url_rejects_non_http():
    assert _is_valid_url("") is False
    assert _is_valid_url("ftp://example.com") is False
    assert _is_valid_url("rtmp://example.com") is False
    assert _is_valid_url("not-a-url") is False
    assert _is_valid_url("http://") is False  # no host


def test_can_add_playlist_requires_only_url():
    assert _can_add("http://x.com/stream", 0.0) is True
    assert _can_add("", 0.0) is False


def test_can_add_channel_requires_name_and_url():
    assert _can_add("http://x.com/stream", 0.0, "My Channel", "channel") is True
    assert _can_add("http://x.com/stream", 0.0, "", "channel") is False
    assert _can_add("http://x.com/stream", 0.0, "  ", "channel") is False


def test_can_add_rejects_invalid_url():
    assert _can_add("invalid", 0.0) is False
    assert _can_add("", 0.0) is False


def test_can_add_blocks_rapid_submit():
    now = time.time()
    assert _can_add("http://x.com/stream", 0.0) is True
    assert _can_add("http://x.com/stream", now) is False
    assert _can_add("http://x.com/stream", now - ADD_CONTENT_COOLDOWN - 1) is True
