"""Tests for HTTP client singleton."""

import httpx

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
