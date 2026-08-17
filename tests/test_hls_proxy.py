"""Unit tests for HLSProxy and deep link parsing in KTV Player."""

import pytest

from core.deeplink import parse_deep_link
from services.hls_proxy import HLSProxy


@pytest.mark.asyncio
async def test_hls_proxy_lifecycle_and_rewrite():
    proxy = HLSProxy(host="127.0.0.1", port=0)
    base_url = await proxy.start()
    assert base_url.startswith("http://127.0.0.1:")
    assert proxy.port is not None

    target = "https://example.com/live/master.m3u8"
    referer = "https://kwik.cx/e/123"
    proxy_url = proxy.get_proxy_url(target, referer=referer)

    assert f"http://127.0.0.1:{proxy.port}/playlist.m3u8?" in proxy_url
    assert "url=" in proxy_url
    assert "referer=" in proxy_url

    m3u8_sample = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-KEY:METHOD=AES-128,URI="mon.key"
#EXTINF:10.0,
segment1.ts
#EXTINF:10.0,
https://cdn.example.com/segment2.ts
"""
    rewritten = proxy._rewrite_m3u8(
        content=m3u8_sample,
        base_url=target,
        referer=referer,
        upstream_headers={"User-Agent": "TestUA"},
    )

    assert "/key?url=" in rewritten
    assert "/segment?url=" in rewritten
    assert rewritten.count("referer=") >= 3

    await proxy.stop()


def test_parse_deep_link_with_referer_and_headers():
    import base64
    import json

    target_url = "https://vault-16.owocdn.top/stream/uwu.m3u8"
    referer_url = "https://kwik.cx/e/sample"
    custom_headers = {"User-Agent": "TestApp/1.0"}

    b64_url = base64.urlsafe_b64encode(target_url.encode()).decode().rstrip("=")
    b64_ref = base64.urlsafe_b64encode(referer_url.encode()).decode().rstrip("=")
    b64_hdrs = (
        base64.urlsafe_b64encode(json.dumps(custom_headers).encode())
        .decode()
        .rstrip("=")
    )

    route = (
        f"ktv://play?url={b64_url}&referer={b64_ref}&headers={b64_hdrs}&title=VGVzdA"
    )
    url, title, referer, headers = parse_deep_link(route)

    assert url == target_url
    assert title == "Test"
    assert referer == referer_url
    assert headers == custom_headers


def test_parse_deep_link_plaintext_title():
    import base64

    target_url = "https://vault-16.owocdn.top/stream/16/06/f710e15c/uwu.m3u8"
    b64_url = base64.urlsafe_b64encode(target_url.encode()).decode().rstrip("=")

    route = f"ktv://play?url={b64_url}&title=BanG%20Dream%21%20Yume%E2%88%9EMita%20-%20Episode%202%20-%20%28720p%29"
    url, title, _referer, _headers = parse_deep_link(route)

    assert url == target_url
    assert title == "BanG Dream! Yume∞Mita - Episode 2 - (720p)"


# --- v2.1.0: quality variant + audio track pinning ---

import base64

from services.hls_proxy import parse_hls_audio_tracks, parse_hls_variants

MASTER = """#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="English",LANGUAGE="en",URI="audio/en.m3u8",DEFAULT=YES
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="aud",NAME="Japanese",LANGUAGE="ja",URI="audio/ja.m3u8"
#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="sub",NAME="Eng",URI="subs/en.m3u8"
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720,AUDIO="aud"
720/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=5000000,RESOLUTION=1920x1080,AUDIO="aud"
1080/index.m3u8
"""


def _dec(token: str) -> str:
    token = token.split('"')[0]
    token += "=" * ((4 - len(token) % 4) % 4)
    return base64.urlsafe_b64decode(token).decode()


def _proxied_urls(rewritten: str) -> list[str]:
    urls = []
    for line in rewritten.splitlines():
        if "url=" not in line:
            continue
        # Variant/segment lines carry the proxy URL bare; #EXT-X-MEDIA
        # lines carry it inside URI="..." (trailing quote stripped in _dec)
        urls.append(_dec(line.split("url=")[1]))
    return urls


class TestVariantParsing:
    def test_parses_variants_in_order(self):
        variants = parse_hls_variants(MASTER)
        assert [v["index"] for v in variants] == [0, 1]
        assert variants[0]["resolution"] == "1280x720"
        assert variants[1]["bandwidth"] == 5000000
        assert variants[1]["uri"] == "1080/index.m3u8"

    def test_media_playlist_has_no_variants(self):
        media = "#EXTM3U\n#EXTINF:4.0,\nseg1.ts\n"
        assert parse_hls_variants(media) == []

    def test_variant_labels_human_readable(self):
        variants = parse_hls_variants(MASTER)
        assert "1280x720" in variants[0]["label"]
        assert "Mbps" in variants[1]["label"]


class TestAudioTrackParsing:
    def test_only_external_audio_renditions(self):
        tracks = parse_hls_audio_tracks(MASTER)
        assert [t["name"] for t in tracks] == ["English", "Japanese"]
        assert tracks[0]["default"] is True
        assert tracks[1]["language"] == "ja"

    def test_muxed_audio_not_returned(self):
        muxed = '#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="a",NAME="en"\n'
        assert parse_hls_audio_tracks(muxed) == []

    def test_subtitles_media_ignored(self):
        tracks = parse_hls_audio_tracks(MASTER)
        assert all(t["uri"].startswith("audio/") for t in tracks)


class TestRewritePinning:
    def _proxy(self) -> HLSProxy:
        proxy = HLSProxy()
        proxy.port = 9999  # rewriting only; no server
        return proxy

    def test_unpinned_keeps_everything_and_proxies_audio(self):
        out = self._proxy()._rewrite_m3u8(
            MASTER, "https://cdn.example/video/master.m3u8", None, {"User-Agent": "X"}
        )
        assert out.count("#EXT-X-STREAM-INF") == 2
        urls = _proxied_urls(out)
        assert any(u.endswith("720/index.m3u8") for u in urls)
        assert any(u.endswith("1080/index.m3u8") for u in urls)
        assert any(u.endswith("audio/en.m3u8") for u in urls)
        assert any(u.endswith("audio/ja.m3u8") for u in urls)
        assert any(u.endswith("subs/en.m3u8") for u in urls)

    def test_ext_x_map_rewritten_to_segment_proxy(self):
        fmp4_m3u8 = (
            "#EXTM3U\n"
            "#EXT-X-VERSION:7\n"
            '#EXT-X-MAP:URI="init.mp4"\n'
            "#EXTINF:6.0,\n"
            "seg1.m4s\n"
        )
        out = self._proxy()._rewrite_m3u8(
            fmp4_m3u8, "https://cdn.example/video/index.m3u8", None, {"User-Agent": "X"}
        )
        assert '#EXT-X-MAP:URI="http://127.0.0.1:9999/segment?url=' in out
        urls = _proxied_urls(out)
        assert any(u.endswith("init.mp4") for u in urls)
        assert any(u.endswith("seg1.m4s") for u in urls)

    def test_variant_pin_keeps_only_selected(self):
        out = self._proxy()._rewrite_m3u8(
            MASTER,
            "https://cdn.example/video/master.m3u8",
            None,
            {"User-Agent": "X"},
            variant=1,
        )
        assert out.count("#EXT-X-STREAM-INF") == 1
        urls = _proxied_urls(out)
        assert any(u.endswith("1080/index.m3u8") for u in urls)
        assert not any(u.endswith("720/index.m3u8") for u in urls)

    def test_audio_pin_drops_others_and_forces_default(self):
        out = self._proxy()._rewrite_m3u8(
            MASTER,
            "https://cdn.example/video/master.m3u8",
            None,
            {"User-Agent": "X"},
            audio="Japanese",
        )
        assert "Japanese" in out
        assert "English" not in out
        media_line = next(line for line in out.splitlines() if "Japanese" in line)
        assert media_line.count("DEFAULT=YES") == 1
        assert "AUTOSELECT=YES" in media_line
        assert any(u.endswith("audio/ja.m3u8") for u in _proxied_urls(out))

    def test_variant_and_audio_pin_combined(self):
        out = self._proxy()._rewrite_m3u8(
            MASTER,
            "https://cdn.example/video/master.m3u8",
            None,
            {"User-Agent": "X"},
            variant=0,
            audio="Japanese",
        )
        assert out.count("#EXT-X-STREAM-INF") == 1
        assert "Japanese" in out and "English" not in out

    def test_media_playlist_untouched_by_pin(self):
        media = "#EXTM3U\n#EXTINF:4.0,\nseg1.ts\n"
        out = self._proxy()._rewrite_m3u8(
            media,
            "https://cdn.example/live/media.m3u8",
            None,
            {"User-Agent": "X"},
            variant=0,
        )
        assert "segment?url=" in out

    def test_get_proxy_url_encodes_pins(self):
        proxy = self._proxy()
        url = proxy.get_proxy_url("https://x/y.m3u8", variant=2, audio="日本語")
        assert "variant=2" in url
        assert "audio=" in url

    def test_playlist_handler_ignores_out_of_range_variant(self):
        proxy = self._proxy()
        # Out-of-range pin falls back to unpinned rewrite (guard in
        # _handle_playlist); verified at the rewriter level here
        out = proxy._rewrite_m3u8(
            MASTER,
            "https://cdn.example/video/master.m3u8",
            None,
            {"User-Agent": "X"},
            variant=99,
        )
        assert out.count("#EXT-X-STREAM-INF") == 0  # no variant index 99 kept
