"""Shared httpx client for all services."""

import httpx


_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


async def close_http_client():
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
