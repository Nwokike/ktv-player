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
