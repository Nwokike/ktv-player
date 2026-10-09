"""Phase 4 — playlist fetch: typed errors, caps, validation, cancellation."""

import asyncio
from unittest import mock

import httpx
import pytest

from services.iptv_service import PlaylistFetchError, iptv_service


def _stream_client(text=None, error=None, status=200):
    """Fake client exposing .stream() as an async context manager."""
    client = mock.MagicMock()

    class _Resp:
        def raise_for_status(self):
            if status != 200:
                raise httpx.HTTPStatusError("bad", request=None, response=None)

        async def aiter_bytes(self, chunk_size=65536):
            data = (text or "").encode("utf-8")
            for i in range(0, len(data), chunk_size):
                yield data[i : i + chunk_size]

    class _CM:
        async def __aenter__(self):
            if error is not None:
                raise error
            return _Resp()

        async def __aexit__(self, *exc):
            return False

    client.stream = mock.MagicMock(return_value=_CM())
    return client


M3U = "#EXTM3U\n#EXTINF:-1,One\nhttp://example.com/1.m3u8\n"


@pytest.mark.asyncio
async def test_fetch_success_parses():
    with mock.patch.object(
        type(iptv_service), "get_client", return_value=_stream_client(M3U)
    ):
        channels = await iptv_service.fetch_playlist("http://example.com/list.m3u")
    assert len(channels) == 1
    assert channels[0]["url"] == "http://example.com/1.m3u8"


@pytest.mark.asyncio
async def test_fetch_http_error_raises_typed():
    client = _stream_client(status=404)
    with (
        mock.patch.object(type(iptv_service), "get_client", return_value=client),
        pytest.raises(PlaylistFetchError) as ei,
    ):
        await iptv_service.fetch_playlist("http://example.com/list.m3u")
    assert ei.value.url == "http://example.com/list.m3u"


@pytest.mark.asyncio
async def test_fetch_invalid_url_raises_before_network():
    client = _stream_client(M3U)
    with mock.patch.object(type(iptv_service), "get_client", return_value=client):
        with pytest.raises(PlaylistFetchError):
            await iptv_service.fetch_playlist("not a url")
        with pytest.raises(PlaylistFetchError):
            await iptv_service.fetch_playlist("ftp://example.com/x.m3u")
    client.stream.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_oversize_raises():
    big = "#EXTM3U\n" + ("#EXTINF:-1,X\nhttp://example.com/x\n" * 500000)
    client = _stream_client(big)
    with (
        mock.patch.object(type(iptv_service), "get_client", return_value=client),
        pytest.raises(PlaylistFetchError),
    ):
        await iptv_service.fetch_playlist("http://example.com/big.m3u")


@pytest.mark.asyncio
async def test_fetch_cancellation_propagates():
    def _cancelled(*a, **k):
        raise asyncio.CancelledError()

    client = mock.MagicMock()
    client.stream = mock.MagicMock(side_effect=_cancelled)
    with (
        mock.patch.object(type(iptv_service), "get_client", return_value=client),
        pytest.raises(asyncio.CancelledError),
    ):
        await iptv_service.fetch_playlist("http://example.com/list.m3u")


def test_error_carries_url_and_cause():
    err = PlaylistFetchError("http://x", ValueError("bad"))
    assert err.url == "http://x"
    assert isinstance(err.cause, ValueError)
    assert "http://x" in str(err)
