"""Tests for HomeScreen component — pure helpers."""

from app_next.screens.home_screen import HomeScreen
from app_next.utils.channels import (
    build_channels_map as _build_channels_map,
)
from app_next.utils.channels import (
    build_favorites_set as _build_favorites_set,
)
from app_next.utils.channels import (
    extract_categories as _extract_categories,
)
from app_next.utils.channels import (
    extract_countries as _extract_countries,
)


def test_home_screen_marked_as_component():
    assert getattr(HomeScreen, "__is_component__", False) is True


def test_build_channels_map_returns_dict_keyed_by_url():
    channels = [
        {"url": "http://a", "name": "A"},
        {"url": "http://b", "name": "B"},
    ]
    m = _build_channels_map(channels)
    assert m["http://a"]["name"] == "A"
    assert m["http://b"]["name"] == "B"


def test_build_channels_map_skips_channels_without_url():
    channels = [
        {"url": "http://a", "name": "A"},
        {"name": "NoURL"},
    ]
    m = _build_channels_map(channels)
    assert "http://a" in m
    assert len(m) == 1


def test_build_favorites_set_from_set():
    class FakeState:
        favorites = {"http://fav1", "http://fav2"}  # noqa: RUF012

    s = _build_favorites_set(FakeState())
    assert s == {"http://fav1", "http://fav2"}


def test_build_favorites_set_from_list():
    class FakeState:
        favorites = ["http://fav1", "http://fav2"]  # noqa: RUF012

    s = _build_favorites_set(FakeState())
    assert s == {"http://fav1", "http://fav2"}


def test_extract_countries_from_channels():
    channels = [
        {"url": "http://a", "group": "Nigeria;Sports", "country_code": "M3U"},
        {"url": "http://b", "group": "Nigeria;News", "country_code": "M3U"},
        {"url": "http://c", "group": "Ghana;General", "country_code": "M3U"},
        {"url": "http://d", "group": "General", "country_code": ""},
    ]
    c = _extract_countries(channels)
    assert "Nigeria" in c
    assert "Ghana" in c
    assert "General" not in c


def test_extract_categories_deduplicates():
    channels = [
        {"url": "http://a", "group": "Nigeria;Sports"},
        {"url": "http://b", "group": "Nigeria;Sports"},
        {"url": "http://c", "group": "Nigeria;News"},
    ]
    c = _extract_categories(channels)
    assert "News" in c
    assert len(c) == 2


def test_extract_country_counts():
    from app_next.utils.channels import extract_country_counts

    channels = [
        {"url": "http://a", "group": "Nigeria;Sports", "country_code": "M3U"},
        {"url": "http://b", "group": "Nigeria;News", "country_code": "M3U"},
        {"url": "http://c", "group": "Ghana;General", "country_code": "M3U"},
    ]
    counts = extract_country_counts(channels)
    assert counts == {"Nigeria": 2, "Ghana": 1}


def test_extract_category_counts():
    from app_next.utils.channels import extract_category_counts

    channels = [
        {"url": "http://a", "group": "Nigeria;Sports"},
        {"url": "http://b", "group": "Nigeria;Sports"},
        {"url": "http://c", "group": "Nigeria;News"},
    ]
    counts = extract_category_counts(channels)
    assert counts == {"Sports": 2, "News": 1}
