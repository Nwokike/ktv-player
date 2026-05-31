"""Tests for the M3U playlist parser."""

import pytest

from src.services.m3u_parser import parse_m3u_text


def test_parse_valid_extinf():
    text = '#EXTINF:-1 tvg-logo="http://logo.png" group-title="News",CNN\nhttp://example.com/stream.m3u8'
    result = parse_m3u_text(text)
    assert len(result) == 1
    assert result[0]["name"] == "CNN"
    assert result[0]["url"] == "http://example.com/stream.m3u8"
    assert result[0]["logo"] == "http://logo.png"
    assert result[0]["group"] == "News"


def test_parse_multiple_channels():
    text = (
        '#EXTINF:-1 group-title="Sports",ESPN\n'
        "http://espn.com/stream.m3u8\n"
        '#EXTINF:-1 group-title="News",BBC\n'
        "http://bbc.com/stream.m3u8\n"
    )
    result = parse_m3u_text(text)
    assert len(result) == 2
    assert result[0]["name"] == "ESPN"
    assert result[1]["name"] == "BBC"


def test_parse_missing_name():
    text = "#EXTINF:-1,\nhttp://example.com/stream.m3u8"
    result = parse_m3u_text(text)
    assert len(result) == 1
    assert result[0]["name"] == "Unknown"


def test_parse_no_extinf_skips_url():
    text = "http://example.com/stream.m3u8\n"
    result = parse_m3u_text(text)
    assert len(result) == 0


def test_parse_extinf_without_url():
    text = '#EXTINF:-1 group-title="News",CNN\n'
    result = parse_m3u_text(text)
    assert len(result) == 0


def test_parse_invalid_url_scheme():
    text = "#EXTINF:-1,FTP Stream\nftp://example.com/stream.m3u8"
    result = parse_m3u_text(text)
    assert len(result) == 0


def test_parse_default_group():
    text = "#EXTINF:-1,Unknown\nhttp://example.com/stream.m3u8"
    result = parse_m3u_text(text, default_group="Custom")
    assert result[0]["group"] == "Custom"


def test_parse_empty_text():
    assert parse_m3u_text("") == []
    assert parse_m3u_text("  ") == []
    assert parse_m3u_text("\n\n\n") == []


def test_parse_url_without_host():
    text = "#EXTINF:-1,Minimal URL\nhttp://"
    result = parse_m3u_text(text)
    assert len(result) == 1
    assert result[0]["url"] == "http://"


def test_parse_complex_tvg_logo():
    text = '#EXTINF:-1 tvg-logo="https://example.com/logo?size=large&format=png" group-title="News",CNN\nhttp://example.com/stream'
    result = parse_m3u_text(text)
    assert result[0]["logo"] == "https://example.com/logo?size=large&format=png"


def test_parse_extinf_with_extra_tags():
    text = '#EXTINF:-1 tvg-id="cnn.us" tvg-name="CNN" tvg-logo="http://logo.png" group-title="News",CNN\nhttp://example.com/stream'
    result = parse_m3u_text(text)
    assert result[0]["name"] == "CNN"
    assert result[0]["logo"] == "http://logo.png"
    assert result[0]["group"] == "News"


def test_parse_channel_with_hyphen_name():
    text = (
        '#EXTINF:-1 group-title="Kids",Cartoon-Network-HD\n'
        "http://example.com/cartoon.m3u8"
    )
    result = parse_m3u_text(text)
    assert result[0]["name"] == "Cartoon-Network-HD"


def test_parse_malformed_extinf_commas_in_meta():
    text = '#EXTINF:-1 group-title="News",CNN,Extra\nhttp://example.com/stream'
    result = parse_m3u_text(text)
    assert result[0]["name"] == "Extra"


def test_parse_multiline_comments_before_url():
    text = (
        '#EXTINF:-1 group-title="Movies",Movie Channel\n'
        "# This is a comment\n"
        "# Another comment\n"
        "http://example.com/movie.m3u8\n"
    )
    result = parse_m3u_text(text)
    assert len(result) == 1
    assert result[0]["name"] == "Movie Channel"


def test_parse_relative_url_rejected():
    text = "#EXTINF:-1,Local\n/relative/path/stream.m3u8"
    result = parse_m3u_text(text)
    assert len(result) == 0
