"""Tests for AddCustomContentDialog pure helpers."""

import time

from components.add_custom_content_dialog import (
    ADD_CONTENT_COOLDOWN,
    _can_add,
    _format_name,
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


def test_can_add_enforces_name_length():
    assert _can_add("Valid Name", "http://x", 0.0) is True
    assert _can_add("", "http://x", 0.0) is False
    name_too_long = "x" * 201
    assert _can_add(name_too_long, "http://x", 0.0) is False


def test_can_add_enforces_url_validation():
    assert _can_add("Test", "invalid", 0.0) is False


def test_can_add_blocks_rapid_submit():
    now = time.time()
    assert _can_add("Test", "http://x", 0.0) is True
    assert _can_add("Test", "http://x", now) is False
    assert _can_add("Test", "http://x", now - ADD_CONTENT_COOLDOWN - 1) is True


def test_format_name_provides_fallback():
    assert _format_name("", "playlist") == "Unnamed Playlist"
    assert _format_name("", "channel") == "Unnamed Channel"
    assert _format_name("My Channel", "channel") == "My Channel"
    assert _format_name("  Trimmed  ", "playlist") == "Trimmed"
