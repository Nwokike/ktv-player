"""Tests for the pure apply_filters helper."""

from app_next.hooks.apply_filters import _default_filters, apply_filters


def _ch(name, url, group="General", is_custom=False, country_code="M3U"):
    return {
        "name": name,
        "url": url,
        "group": group,
        "is_custom": is_custom,
        "country_code": country_code,
    }


def test_default_filters_returns_all_channels_capped():
    channels = [_ch(f"c{i}", f"http://x/{i}") for i in range(100)]
    out = apply_filters(channels, _default_filters(), favorites_set=set())
    assert len(out) <= 50  # MAX_SEARCH_RESULTS cap
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


def test_source_built_in_excludes_custom_channels():
    channels = [
        _ch("A", "http://a", is_custom=False),
        _ch("B", "http://b", is_custom=True),
    ]
    out = apply_filters(channels, {**_default_filters(), "source": "built-in"}, set())
    assert [c["name"] for c in out] == ["A"]


def test_source_custom_keeps_only_custom():
    channels = [
        _ch("A", "http://a", is_custom=False),
        _ch("B", "http://b", is_custom=True),
    ]
    out = apply_filters(channels, {**_default_filters(), "source": "custom"}, set())
    assert [c["name"] for c in out] == ["B"]


def test_source_all_keeps_both():
    channels = [
        _ch("A", "http://a", is_custom=False),
        _ch("B", "http://b", is_custom=True),
    ]
    out = apply_filters(channels, _default_filters(), set())
    assert len(out) == 2


def test_filters_compose():
    channels = [
        _ch("A", "http://a", group="Nigeria;Sports", is_custom=True),
        _ch("B", "http://b", group="Nigeria;Sports", is_custom=False),
        _ch("C", "http://c", group="Nigeria;News", is_custom=True),
    ]
    f = {
        **_default_filters(),
        "country": "Nigeria",
        "category": "Nigeria;Sports",
        "source": "custom",
    }
    out = apply_filters(channels, f, set())
    assert [c["name"] for c in out] == ["A"]
