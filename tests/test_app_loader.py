"""Regression tests for core.app_loader.load_all_channels.

These tests exercise the real load_all_channels() function — they mock only
the I/O dependencies (channel_provider, db_manager, iptv_service), not the
loader itself. This catches bugs in the loader's body (e.g. dangling imports
of deleted modules) that a fully-mocked test would silently miss.
"""

from unittest import mock

import pytest

from core.app_loader import load_all_channels
from core.state import state


class _Lock:
    """Stand-in for asyncio.Lock that records `locked()` state."""

    def __init__(self, val: bool = False):
        self._locked = val
        self.locked = lambda: self._locked

    async def __aenter__(self):
        self._locked = True
        return self

    async def __aexit__(self, *exc):
        self._locked = False


class _FakePage:
    def __init__(self):
        self._dialogs = []

    def show_dialog(self, dialog):
        self._dialogs.append(dialog)

    def update(self, *a, **k):
        pass


@pytest.fixture(autouse=True)
def _patch_io():
    """Mock I/O deps so load_all_channels() runs without network/Disk."""
    provider = mock.AsyncMock()
    provider.get_all_channels.return_value = [
        {
            "url": "http://a",
            "name": "A",
            "group": "Nigeria;Sports",
            "country_code": "M3U",
        },
    ]

    dbm = mock.AsyncMock()
    dbm.get_custom_channels.return_value = []
    dbm.get_playlists.return_value = []

    iptv = mock.AsyncMock()

    with (
        mock.patch("core.app_loader.channel_provider", provider),
        mock.patch("core.app_loader.db_manager", dbm),
        mock.patch("core.app_loader.iptv_service", iptv),
    ):
        yield provider, dbm, iptv


@pytest.mark.anyio
async def test_load_all_channels_does_not_crash_on_dangling_imports():
    """Regression: load_all_channels() must not import a deleted module.

    Prior bug (2026-07-28): the body had
        `from views.tabs.channel_classification import _invalidate_groups_cache`
    but views.tabs.channel_classification.py was removed in the frontend
    rewrite commit. Running load_all_channels() raised ModuleNotFoundError,
    silently swallowed by onboarding's try/except → channels never loaded.
    """
    # Capture & clear state before
    state.set_channels([])

    await load_all_channels(_FakePage(), _Lock())

    # The channel should be loaded into observable state.
    assert any(c.get("url") == "http://a" for c in state.channels), (
        f"expected channels loaded into state, got {state.channels}"
    )


@pytest.mark.anyio
async def test_load_all_channels_merges_custom_channels_marked_is_custom():
    dbm = mock.AsyncMock()
    dbm.get_custom_channels.return_value = [
        {"url": "http://custom", "name": "My Channel", "group": "Custom"},
    ]
    dbm.get_playlists.return_value = []
    provider = mock.AsyncMock()
    provider.get_all_channels.return_value = [
        {"url": "http://builtin", "name": "Built-in"},
    ]
    with (
        mock.patch("core.app_loader.channel_provider", provider),
        mock.patch("core.app_loader.db_manager", dbm),
        mock.patch("core.app_loader.iptv_service", mock.AsyncMock()),
    ):
        state.set_channels([])
        await load_all_channels(_FakePage(), _Lock())

    by_url = {c["url"]: c for c in state.channels}
    assert by_url["http://custom"]["is_custom"] is True
    assert by_url.get("http://builtin", {}).get("is_custom") in (None, False)
