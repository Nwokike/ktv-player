"""Tests for AppController.init() mounting the component frontend."""

from unittest import mock

import pytest

from src.main import AppController


def _make_controller(fake_page):
    return AppController(fake_page)


@pytest.fixture(autouse=True)
def _patch_services():
    """Set up all mocks needed for init() to complete without I/O."""
    dbm = mock.AsyncMock()
    dbm.init_db.return_value = None
    dbm.get_setting.return_value = None
    dbm.get_favorite_urls.return_value = set()
    dbm.get_history.return_value = []
    dbm.load_liveliness_cache.return_value = {}

    ads = mock.AsyncMock()
    ads.gather_consent.return_value = None
    ads.preload_interstitial.return_value = None

    with (
        mock.patch("src.main.db_manager", dbm),
        mock.patch("src.main.AdService", return_value=ads),
        mock.patch("src.main.LivelinessChecker"),
        mock.patch("src.services.liveliness.liveliness_cache.load_from_db"),
    ):
        yield


@pytest.mark.anyio
async def test_init_renders_appshell(fake_page):
    """init() always mounts the component frontend via page.render()."""
    controller = _make_controller(fake_page)

    async def _noop(*a, **k):
        return None

    with mock.patch("src.main.AppController.load_channels", _noop):
        await controller.init()

    assert len(fake_page.render_calls) == 1
