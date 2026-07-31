"""Tests for the pure apply_filters helper."""

from hooks.apply_filters import _default_filters, apply_filters


def _ch(
    name,
    url,
    group="General",
    is_custom=False,
    country_code="M3U",
    is_single_custom=False,
):
    return {
        "name": name,
        "url": url,
        "group": group,
        "is_custom": is_custom,
        "is_single_custom": is_single_custom,
        "country_code": country_code,
    }


def test_default_filters_returns_all_channels():
    channels = [_ch(f"c{i}", f"http://x/{i}") for i in range(100)]
    out = apply_filters(channels, _default_filters(), favorites_set=set())
    assert len(out) == 100
    assert out[0] == channels[0]


def test_country_filter_keeps_only_matching_country_segment():
    channels = [
        _ch("A", "http://a", group="Nigeria;Sports"),
        _ch("B", "http://b", group="Ghana;News"),
    ]
    out = apply_filters(channels, {**_default_filters(), "country": "Nigeria"}, set())
    assert [c["name"] for c in out] == ["A"]


def test_country_filter_all_keeps_everything():
    channels = [
        _ch("A", "http://a", group="Nigeria"),
        _ch("B", "http://b", group="Ghana"),
    ]
    out = apply_filters(channels, _default_filters(), set())
    assert len(out) == 2


def test_category_filter_matches_full_group_string():
    channels = [
        _ch("A", "http://a", group="Nigeria;Sports"),
        _ch("B", "http://b", group="Nigeria;News"),
    ]
    out = apply_filters(
        channels, {**_default_filters(), "category": "Nigeria;Sports"}, set()
    )
    assert [c["name"] for c in out] == ["A"]


def test_fav_only_filter_keeps_only_favorites():
    channels = [_ch("A", "http://a"), _ch("B", "http://b")]
    out = apply_filters(
        channels, {**_default_filters(), "fav_only": True}, favorites_set={"http://a"}
    )
    assert [c["name"] for c in out] == ["A"]


def test_fav_only_with_empty_favorites_returns_empty():
    channels = [_ch("A", "http://a")]
    out = apply_filters(channels, {**_default_filters(), "fav_only": True}, set())
    assert out == []


def test_country_filter_excludes_custom_channels():
    channels = [
        _ch("A", "http://a", group="Nigeria;Sports", is_custom=False),
        _ch("B", "http://b", group="Nigeria;Sports", is_custom=True),
    ]
    out = apply_filters(channels, {**_default_filters(), "country": "Nigeria"}, set())
    assert [c["name"] for c in out] == ["A"]


def test_custom_all_keeps_only_custom():
    channels = [
        _ch("A", "http://a", is_custom=False),
        _ch("B", "http://b", is_custom=True),
    ]
    out = apply_filters(channels, {**_default_filters(), "custom": "all"}, set())
    assert [c["name"] for c in out] == ["B"]


def test_custom_single_keeps_only_single():
    channels = [
        _ch("A", "http://a", group="Sports", is_custom=True, is_single_custom=False),
        _ch("B", "http://b", is_custom=True, is_single_custom=True),
    ]
    out = apply_filters(channels, {**_default_filters(), "custom": "single"}, set())
    assert [c["name"] for c in out] == ["B"]


def test_custom_group_keeps_matching_group():
    channels = [
        _ch("A", "http://a", group="Sports", is_custom=True),
        _ch("B", "http://b", group="News", is_custom=True),
    ]
    out = apply_filters(channels, {**_default_filters(), "custom": "Sports"}, set())
    assert [c["name"] for c in out] == ["A"]
