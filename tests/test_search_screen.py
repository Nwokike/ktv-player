"""Tests for SearchScreen component."""

from app_next.screens.search_screen import SearchScreen, _search_filter


def test_search_screen_marked_as_component():
    assert getattr(SearchScreen, "__is_component__", False) is True


def test_search_filter_matches_channel_name_case_insensitive():
    channels = [
        {"name": "BBC World", "url": "http://bbc"},
        {"name": "CNN International", "url": "http://cnn"},
        {"name": "Al Jazeera", "url": "http://aj"},
    ]
    result = _search_filter(channels, "bbc")
    assert [c["name"] for c in result] == ["BBC World"]


def test_search_filter_empty_query_returns_all_capped():
    channels = [{"name": f"Channel {i}", "url": f"http://x/{i}"} for i in range(100)]
    result = _search_filter(channels, "")
    assert len(result) <= 50  # MAX_SEARCH_RESULTS


def test_search_filter_no_match_returns_empty():
    channels = [{"name": "BBC", "url": "http://bbc"}]
    result = _search_filter(channels, "zzz")
    assert result == []


def test_search_filter_matches_url_as_fallback():
    channels = [{"name": "Test", "url": "http://example.com/stream"}]
    result = _search_filter(channels, "example")
    assert len(result) == 1
