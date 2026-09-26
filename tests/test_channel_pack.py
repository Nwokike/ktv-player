"""Premium channel pack: taxonomy normalization, tier plumbing, guards.

The pack (iptv-org index) stores country ONLY in tvg-id and treats
group-title as an unordered category tag-set. These tests pin the
mapping that keeps every folder: real countries from tvg-id codes,
every tag counted as a category, and the upgrade guards that stop a
swap from stranding a saved filter or a favorite.
"""

import inspect

import pytest

from channels.normalize import (
    normalize_legacy,
    normalize_premium,
    tvg_id_country,
)
from channels.provider import _cache_path, _current_tier
from core import constants as core_constants
from core.constants import premium_pack_url
from core.country_codes import IPTV_ORG_COUNTRIES, country_name
from hooks.apply_filters import _default_filters, apply_filters, reconcile_filters
from utils.channels import extract_category_counts, extract_countries

# Codes that actually occur in the pack index (measured census), plus
# Nigeria, which onboarding saves for the largest local audience.
REAL_PACK_CODES = [
    "us",
    "in",
    "ru",
    "de",
    "se",
    "es",
    "br",
    "it",
    "do",
    "uk",
    "cl",
    "tr",
    "fr",
    "ua",
    "ar",
    "nl",
    "id",
    "pe",
    "ca",
    "mx",
    "cn",
    "hu",
    "ng",
]


# -- tvg-id country extraction ----------------------------------------------


def test_tvg_id_country_handles_both_shapes():
    assert tvg_id_country("1Plus1Marafon.ua@SD") == "ua"
    assert tvg_id_country("Kanali7.al") == "al"
    assert tvg_id_country("ABCTV.au@NSW") == "au"
    assert tvg_id_country("no-dot@SD") is None
    assert tvg_id_country("") is None


def test_every_real_pack_code_resolves_to_a_country_name():
    missing = [c for c in REAL_PACK_CODES if country_name(c) is None]
    assert missing == [], f"country map misses codes present in the pack: {missing}"
    assert country_name("uk") == "United Kingdom"
    assert country_name("ng") == "Nigeria"
    assert len(IPTV_ORG_COUNTRIES) >= 177


# -- legacy normalizer (free base, keeps today's folders) -------------------


def test_legacy_country_groups_keep_their_exact_names():
    (albania,) = normalize_legacy([{"group": "Albania", "url": "u"}])
    assert albania["country"] == "Albania"
    assert albania["categories"] == []
    assert albania["country_code"] == "M3U"

    (japan,) = normalize_legacy([{"group": "日本 / Japan", "url": "u"}])
    assert japan["country"] == "日本 / Japan"


def test_legacy_category_groups_stay_global_categories():
    (news,) = normalize_legacy([{"group": "News", "url": "u"}])
    assert news["country"] == "Global"
    assert news["categories"] == ["News"]
    assert news["country_code"] == ""

    (vod,) = normalize_legacy([{"group": "VOD Italy", "url": "u"}])
    assert vod["country"] == "Global"
    assert vod["categories"] == ["VOD Italy"]


def test_legacy_pair_keeps_the_country_the_old_whole_string_scan_lost():
    # The old classifier saw "news" anywhere in the string and threw the
    # country into Global; the first segment is what decides now.
    (pair,) = normalize_legacy([{"group": "Nigeria;News", "url": "u"}])
    assert pair["country"] == "Nigeria"
    assert pair["categories"] == ["News"]
    assert pair["country_code"] == "M3U"


# -- premium normalizer (the pack) ------------------------------------------


def test_premium_channel_gets_a_real_country_and_every_tag():
    (ch,) = normalize_premium([{"group": "News", "url": "u", "tvg_id": "ACNN.ng@SD"}])
    assert ch["country"] == "Nigeria"
    assert ch["categories"] == ["News"]
    assert ch["country_code"] == "M3U"

    (multi,) = normalize_premium(
        [
            {
                "group": "Culture;Entertainment;Sports;Travel",
                "url": "u",
                "tvg_id": "SomeChannel.ua@HD",
            }
        ]
    )
    assert multi["country"] == "Ukraine"
    assert multi["categories"] == [
        "Culture",
        "Entertainment",
        "Sports",
        "Travel",
    ]


def test_premium_never_invents_fake_country_folders():
    # The old regex turned these tags into country pills
    # (Entertainment/Series/Undefined held 3513 channels).
    for tag in ("Entertainment", "Series", "Undefined", "Documentary"):
        (ch,) = normalize_premium([{"group": tag, "url": "u", "tvg_id": "x.zz@SD"}])
        assert ch["country"] == "Global", tag
        assert ch["country_code"] == ""
        assert ch["categories"] == [tag]

    # Even with no resolvable code the tags survive as categories.
    (no_code,) = normalize_premium([{"group": "News;Public", "url": "u"}])
    assert no_code["country"] == "Global"
    assert no_code["categories"] == ["News", "Public"]


def test_premium_general_tag_is_kept_in_data_but_hidden_from_pills():
    (ch,) = normalize_premium([{"group": "General", "url": "u", "tvg_id": "a.us@SD"}])
    assert ch["country"] == "United States"
    assert ch["categories"] == ["General"]  # hidden later by extractors
    counts = extract_category_counts([ch])
    assert "General" not in counts


# -- extractors and filters over canonical fields ---------------------------


def test_multi_tag_channel_counts_under_every_category():
    channels = normalize_premium(
        [
            {"group": "Animation;Kids", "url": "u1", "tvg_id": "a.us@SD"},
            {"group": "News", "url": "u2", "tvg_id": "b.ng@SD"},
        ]
    )
    counts = extract_category_counts(channels)
    assert counts == {"Animation": 1, "Kids": 1, "News": 1}
    countries = extract_countries(channels)
    assert countries == ["Nigeria", "United States"]


def test_category_filter_matches_any_tag_not_just_the_last_segment():
    channels = normalize_premium(
        [{"group": "Culture;Entertainment;Sports", "url": "u", "tvg_id": "x.it@SD"}]
    )
    for wanted in ("Culture", "Entertainment", "Sports"):
        out = apply_filters(channels, {**_default_filters(), "category": wanted}, set())
        assert len(out) == 1, wanted


def test_country_filter_matches_the_canonical_name():
    channels = normalize_premium([{"group": "News", "url": "u", "tvg_id": "x.ng@SD"}])
    assert (
        len(
            apply_filters(channels, {**_default_filters(), "country": "Nigeria"}, set())
        )
        == 1
    )
    assert (
        len(apply_filters(channels, {**_default_filters(), "country": "Ghana"}, set()))
        == 0
    )


# -- upgrade guard: stranded selections --------------------------------------


def test_reconcile_resets_a_country_that_the_swap_removed():
    filters = {**_default_filters(), "country": "Nigeria", "category": "Sports"}
    out = reconcile_filters(filters, {"Ghana": 5}, {"News": 2})
    assert out["country"] == "all"
    assert out["category"] == "all"  # Sports vanished too


def test_reconcile_keeps_live_selections_and_custom_sentinels():
    filters = {**_default_filters(), "country": "Ghana", "category": "News"}
    out = reconcile_filters(filters, {"Ghana": 5}, {"News": 2})
    assert out == filters

    custom_kept = {**_default_filters(), "custom": "single"}
    assert reconcile_filters(custom_kept, {}, {}, {})["custom"] == "single"

    custom_dead = {**_default_filters(), "custom": "Old Group"}
    assert reconcile_filters(custom_dead, {}, {}, {"New Group": 1})["custom"] == "none"


# -- hash: taxonomy changes must re-render -----------------------------------


def test_channels_hash_moves_when_only_the_group_changes():
    from core.state import state

    try:
        state.set_channels([{"url": "http://a", "group": "Albania"}])
        first = state.channels_hash
        state.set_channels([{"url": "http://a", "group": "News"}])
        second = state.channels_hash
        state.set_channels([{"url": "http://a", "group": "News", "country": "Albania"}])
        third = state.channels_hash
    finally:
        state.set_channels([])
    assert first != second, "group-only change must bump the hash"
    assert second != third, "country-only change must bump the hash"


# -- tier plumbing -----------------------------------------------------------


def test_cache_paths_are_tier_qualified():
    from channels.provider import _CACHE_FILE

    assert _cache_path("free") == _CACHE_FILE
    premium = _cache_path("premium")
    assert premium != _CACHE_FILE
    assert premium.endswith("cached_playlist.premium.m3u8")


def test_premium_pack_url_decodes_and_never_appears_in_plaintext():
    assert premium_pack_url() == "https://iptv-org.github.io/iptv/index.m3u"
    source = inspect.getsource(core_constants)
    assert "iptv-org.github.io" not in source, (
        "the raw aggregator URL must stay base64-encoded in the repo"
    )


def test_current_tier_follows_the_premium_flag():
    from core.state import state

    try:
        state.is_premium = False
        assert _current_tier() == "free"
        state.is_premium = True
        assert _current_tier() == "premium"
    finally:
        state.is_premium = False


def test_load_channels_forwards_force():
    from main import AppController

    src = inspect.getsource(AppController.load_channels)
    assert "force=force" in src, (
        "force must survive main -> app_loader, or a tier flip serves "
        "the in-memory free list forever"
    )


# -- favorites re-key ---------------------------------------------------------


@pytest.mark.asyncio
async def test_favorites_rekey_by_name_on_swap(monkeypatch):
    from unittest import mock

    from core import app_loader
    from core.state import state

    db = mock.Mock()
    stored = [{"url": "http://old", "name": "Al Jazeera English", "logo": ""}]

    async def get_favorites():
        return list(stored)

    async def remap(old, new):
        assert (old, new) == ("http://old", "http://new")
        return True

    async def get_urls():
        return {"http://new"}

    db.get_favorites.side_effect = get_favorites
    db.remap_favorite_url.side_effect = remap
    db.get_favorite_urls.side_effect = get_urls

    channels = [{"url": "http://new", "name": "Al Jazeera English"}]
    old_favs = list(state.favorites)
    try:
        state.favorites = []
        with (
            mock.patch.object(app_loader, "db_manager", db),
            mock.patch("utils.notifications.notify") as notify,
        ):
            await app_loader._reconcile_favorites(channels)
        assert state.favorites == ["http://new"]
        notify.assert_called_once()
        assert "Updated 1 saved channels" in notify.call_args[0][0]
    finally:
        state.favorites = old_favs


@pytest.mark.asyncio
async def test_favorites_orphans_are_kept_silent(monkeypatch):
    from unittest import mock

    from core import app_loader
    from core.state import state

    db = mock.Mock()

    async def get_favorites():
        return [{"url": "http://gone", "name": "Channel That Left", "logo": ""}]

    async def get_urls():
        return {"http://gone"}

    db.get_favorites.side_effect = get_favorites
    db.get_favorite_urls.side_effect = get_urls

    old_favs = list(state.favorites)
    try:
        state.favorites = ["http://gone"]
        with (
            mock.patch.object(app_loader, "db_manager", db),
            mock.patch("utils.notifications.notify") as notify,
        ):
            await app_loader._reconcile_favorites(
                [{"url": "http://other", "name": "Something Else"}]
            )
        # Never deleted, never nagged on a routine refresh.
        db.remap_favorite_url.assert_not_called()
        notify.assert_not_called()
        assert state.favorites == ["http://gone"]
    finally:
        state.favorites = old_favs
