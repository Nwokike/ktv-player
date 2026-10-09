"""Shared httpx client for all services."""

import logging
import threading

import httpx

from core.constants import USER_AGENT

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None
# threading.Lock (not asyncio.Lock): creation holds it for microseconds with
# no awaits inside, so it guards both threads and coroutines without ever
# blocking the event loop — and keeps get_http_client() sync for all 5
# existing call sites.
_client_lock = threading.Lock()


def _build_client() -> httpx.AsyncClient:
    limits = httpx.Limits(
        max_connections=100,
        max_keepalive_connections=30,
        keepalive_expiry=10.0,
    )
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout=10.0, connect=5.0, read=8.0, pool=2.0),
        follow_redirects=True,
        # h2 is installed: same-origin logo/liveliness/playlist fetches
        # collapse onto one multiplexed connection. Transport-level knobs
        # (http2, limits) MUST live on the transport: a custom transport=
        # replaces httpx's default construction, silently dropping any
        # http2=/limits= passed at client level.
        # Per-origin escape hatch for broken IPTV hosts (documented pattern,
        # not wired by default):
        #   mounts={"all://*badhost.example": httpx.AsyncHTTPTransport()}
        transport=httpx.AsyncHTTPTransport(retries=1, http2=True, limits=limits),
        headers={
            "User-Agent": USER_AGENT,
        },
        # Connect-establishment retries only (NOT reads/status): covers
        # flaky mobile connects for playlist/logo/liveliness GET+HEAD.
        # Read/status retry stays manual per call site.
    )


def get_http_client() -> httpx.AsyncClient:
    """Return the shared client, creating it once under a lock."""
    global _client
    if _client is None or _client.is_closed:
        with _client_lock:
            if _client is None or _client.is_closed:
                _client = _build_client()
    return _client


async def close_http_client():
    """SHUTDOWN-ONLY: close the shared client at app exit.

    Single owner is AppController._on_close. Any other holder must NOT call
    this: in-flight requests from other services would fail on the closed
    client, and the next get_http_client() silently rebuilds (pool churn).
    """
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None
