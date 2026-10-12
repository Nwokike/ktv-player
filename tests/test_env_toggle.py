"""Tests for AppController.init() mounting the component frontend."""

from unittest import mock

import pytest

from src.main import AppController


def _make_controller(fake_page):
    return AppController(fake_page)


@pytest.fixture(autouse=True)
def _patch_services():
    """Set up all mocks needed for init() to complete without I/O.

    Per-method mocks (not blanket AsyncMock): PremiumService/AdService mix
    sync and async methods, and AsyncMock turns every sync method into an
    unawaited coroutine (RuntimeWarning + silently skipped behavior, e.g.
    add_listener at src/main.py:119).
    """
    dbm = mock.AsyncMock()
    dbm.init_db.return_value = None
    dbm.get_setting.return_value = None
    dbm.get_favorite_urls.return_value = set()
    dbm.get_history.return_value = []
    dbm.load_liveliness_cache.return_value = {}

    ads = mock.MagicMock()
    ads.gather_consent = mock.AsyncMock(return_value=None)
    ads.preload_interstitial = mock.AsyncMock(return_value=None)
    ads.close = mock.AsyncMock(return_value=None)

    premium = mock.MagicMock()
    premium.add_listener = mock.MagicMock()
    premium.remove_listener = mock.MagicMock()
    premium.load_local = mock.AsyncMock(return_value=None)
    premium.reconcile = mock.AsyncMock(return_value=None)
    premium.reconcile_if_due = mock.AsyncMock(return_value=None)
    premium.start_reconcile_loop = mock.MagicMock()
    premium.stop_reconcile_loop = mock.MagicMock()
    premium.shutdown = mock.MagicMock()

    with (
        mock.patch("src.main.db_manager", dbm),
        mock.patch("src.main.AdService", return_value=ads),
        mock.patch("src.main.PremiumService", return_value=premium),
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


@pytest.mark.anyio
async def test_init_mirrors_premium_onto_the_page(fake_page):
    """Settings reads the premium service off the PAGE, not the controller.

    src/screens/settings_screen.py does
    `premium_service = getattr(page_obj, "premium", None)` and returns early
    when it is None, so without the mirror the whole purchase UI — products,
    checkout, recovery ID — never renders. 2.3.0 dropped the line that sets
    it, which is why premium showed nothing.

    Also pins that init() only calls methods the service actually has: an
    `ashutdown()` that 2.2.0's PremiumService does not implement is swallowed
    by a `contextlib.suppress` and silently leaves the watcher tasks running.
    """
    controller = _make_controller(fake_page)

    async def _noop(*a, **k):
        return None

    with (
        mock.patch.object(controller, "load_channels", _noop),
        mock.patch.object(controller, "route_change", _noop),
    ):
        await controller.init()

    assert fake_page.premium is not None, "page.premium is unset"
    assert fake_page.premium is controller.premium, (
        "page.premium is a different service"
    )
    # The sync cancel-only shutdown is what 2.2.0 exposes.
    assert hasattr(controller.premium, "shutdown")
