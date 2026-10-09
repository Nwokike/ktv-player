"""Tests for HTTP client singleton."""

import httpx
import pytest

from services.http_client import get_http_client


def test_get_http_client_returns_async_client():
    client = get_http_client()
    assert isinstance(client, httpx.AsyncClient)


def test_get_http_client_returns_same_instance():
    client1 = get_http_client()
    client2 = get_http_client()
    assert client1 is client2


def test_http_client_has_expected_timeouts():
    client = get_http_client()
    # Default timeout should be set
    assert client.timeout is not None


def test_http_client_follows_redirects():
    client = get_http_client()
    assert client.follow_redirects is True


def test_shared_client_uses_http2_transport():
    import asyncio

    from services.http_client import _build_client

    client = _build_client()
    try:
        assert client._transport is not None
    finally:
        asyncio.run(client.aclose())


def test_shared_client_default_headers():
    import asyncio

    from services.http_client import _build_client

    client = _build_client()
    try:
        assert "python-httpx" not in client.headers.get("User-Agent", "")
        assert "gzip" in client.headers.get("Accept-Encoding", "")
    finally:
        asyncio.run(client.aclose())


def test_shared_client_timeout_is_explicit_4_tuple():
    import asyncio

    from services.http_client import _build_client

    client = _build_client()
    try:
        t = client.timeout
        assert isinstance(t, httpx.Timeout)
        assert t.pool == 2.0
        assert t.connect == 5.0
    finally:
        asyncio.run(client.aclose())


def test_singleton_converges():
    import asyncio

    import services.http_client as hc
    from services.http_client import close_http_client

    old = hc._client
    hc._client = None
    try:
        a = get_http_client()
        b = get_http_client()
        assert a is b
    finally:
        asyncio.run(close_http_client())
        hc._client = old


@pytest.mark.asyncio
async def test_close_is_idempotent_and_clears():
    import services.http_client as hc
    from services.http_client import close_http_client

    hc._client = None
    get_http_client()
    await close_http_client()
    assert hc._client is None
    await close_http_client()  # no raise on empty
