"""Playlist sidecar tests: roundtrip, invalidation, fallback, compactness."""

import os

from channels.sidecar import _FIELDS, load_sidecar, store_sidecar


def _channels():
    return [
        {
            "url": f"http://s{i}.example/live.m3u8",
            "name": f"Channel {i}",
            "logo": f"http://x/{i}.png",
            "group": "Sports",
            "country": "Nigeria",
            "country_code": "NG",
            "categories": ["Sports"],
            "tvg_id": f"ch{i}",
            "tvg_country": "NG",
            "is_custom": False,
        }
        for i in range(5)
    ]


def test_roundtrip_preserves_channels(tmp_path):
    raw = tmp_path / "cached_playlist.m3u8"
    raw.write_text("#EXTM3U\n", encoding="utf-8")
    channels = _channels()
    store_sidecar(str(raw), channels)
    assert load_sidecar(str(raw)) == channels


def test_missing_sidecar_returns_none(tmp_path):
    raw = tmp_path / "cached_playlist.m3u8"
    raw.write_text("#EXTM3U\n", encoding="utf-8")
    assert load_sidecar(str(raw)) is None


def test_missing_raw_returns_none(tmp_path):
    assert load_sidecar(str(tmp_path / "nope.m3u8")) is None


def test_raw_change_invalidates_sidecar(tmp_path):
    raw = tmp_path / "cached_playlist.m3u8"
    raw.write_text("#EXTM3U\n", encoding="utf-8")
    store_sidecar(str(raw), _channels())
    assert load_sidecar(str(raw)) is not None
    # Refresh rewrites the raw file: mtime+size change kills the sidecar.
    raw.write_text("#EXTM3U\n#EXTINF:-1,X\nhttp://new.example/x\n", encoding="utf-8")
    assert load_sidecar(str(raw)) is None


def test_corrupt_sidecar_returns_none(tmp_path):
    raw = tmp_path / "cached_playlist.m3u8"
    raw.write_text("#EXTM3U\n", encoding="utf-8")
    store_sidecar(str(raw), _channels())
    with open(str(raw) + ".mpk", "wb") as f:
        f.write(b"\x00\x01not msgpack at all\xff")
    assert load_sidecar(str(raw)) is None


def test_old_schema_version_mismatches(tmp_path):
    import msgpack

    raw = tmp_path / "cached_playlist.m3u8"
    raw.write_text("#EXTM3U\n", encoding="utf-8")
    st = os.stat(str(raw))
    with open(str(raw) + ".mpk", "wb") as f:
        f.write(
            msgpack.packb(
                {"v": 1, "mtime": st.st_mtime, "size": st.st_size, "channels": []},
                use_bin_type=True,
            )
        )
    assert load_sidecar(str(raw)) is None


def test_sidecar_is_compact_and_smaller_than_dicts(tmp_path):
    import msgpack

    raw = tmp_path / "cached_playlist.m3u8"
    raw.write_text("#EXTM3U\n", encoding="utf-8")
    channels = _channels()
    store_sidecar(str(raw), channels)
    mpk_size = os.path.getsize(str(raw) + ".mpk")
    dict_size = len(msgpack.packb(channels, use_bin_type=True))
    assert mpk_size < dict_size, f"sidecar {mpk_size} not smaller than {dict_size}"


def test_fields_cover_normalize_contract():
    """The positional order must include every key the parser emits or
    normalize adds, or _decode silently drops data on step-down."""
    import inspect

    import channels.normalize as norm
    import services.m3u_parser as parser

    combined = inspect.getsource(norm) + inspect.getsource(parser)
    for field in _FIELDS:
        assert f'"{field}"' in combined or f"'{field}'" in combined, field
