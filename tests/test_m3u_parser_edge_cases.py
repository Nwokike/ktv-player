"""Tests for M3U parser edge cases not already covered."""

from services.m3u_parser import parse_m3u_text


def test_empty_input():
    result = parse_m3u_text("")
    assert result == []


def test_only_header():
    result = parse_m3u_text("#EXTM3U")
    assert result == []


def test_malformed_extinf():
    text = "#EXTINF:-1,Bad Entry\nhttp://url"
    result = parse_m3u_text(text)
    assert len(result) == 1


def test_url_without_extinf():
    text = "#EXTM3U\nhttp://stream.without.meta"
    result = parse_m3u_text(text)
    # Parser only collects URLs that follow #EXTINF: tags
    assert len(result) == 0


def test_mixed_content():
    text = """#EXTM3U
#EXTINF:-1,Channel One
http://one.com
#EXTINF:-1,Channel Two
http://two.com
# some comment
#EXTINF:-1,Channel Three  
http://three.com"""
    result = parse_m3u_text(text)
    assert len(result) == 3
