"""Checkout watcher + entitlement reconciler.

The watcher is what turns "you paid, now press Restore" into "the screen
flips by itself": started by kiri_checkout, it polls restore every few
seconds until the server confirms. The reconciler is the steady-state half
(hourly + on foreground resume) and — critically — it uses the
token-issuing path, because a status-only reply can never re-arm a token
and a renewal would otherwise lock a paying subscriber out at the old
exp (see PremiumService.reconcile).
"""

import asyncio
import time

import pytest

from core.state import state
from services.kiri_license import KiriLicenseService
from services.premium_service import PremiumService
from tests.license_fixtures import PUBLIC_KEY, TOKENS

RECOVERY = "KIRI-M-FIXTURE0000000000000000"


class _TaskPage:
    """Page whose run_task really runs — captures tasks for cancellation asserts."""

    def __init__(self):
        self.tasks = []

    def run_task(self, fn, *args):
        task = asyncio.get_running_loop().create_task(fn(*args))
        self.tasks.append(task)
        return task


def _service(page=None):
    premium = PremiumService(page if page is not None else _TaskPage())
    # Fixture key pair: the tokens must verify against this suite's key,
    # not the production key baked into KiriLicenseService's default.
    premium.license = KiriLicenseService(
        public_key=PUBLIC_KEY, on_change=premium._recompute_premium
    )
    return premium


def _dbm(store=None):
    from unittest import mock

    store = {} if store is None else store
    dbm = mock.AsyncMock()

    async def get_setting(key, default=""):
        return store.get(key, default)

    async def set_setting(key, value):
        store[key] = value

    dbm.get_setting.side_effect = get_setting
    dbm.set_setting.side_effect = set_setting
    return dbm


def _http(script, urls):
    """Async post over a script of bodies/exceptions; records every URL."""
    from unittest import mock

    client = mock.Mock()

    async def post(url, **kwargs):
        urls.append(str(url))
        if not script:
            raise AssertionError("unexpected extra request")
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        response = mock.Mock()
        response.status_code = item.get("status", 200)
        response.json.return_value = item.get("body", {})
        return response

    client.post = post
    return client


def _active_body():
    # LIFETIME is the only fixture with exp: null — YEARLY_ACTIVE's exp
    # (1790000000 = 21 Sep 2026) is already in the past, and these paths
    # verify against the real clock (the token tests pin `now` instead).
    return {
        "recovery_id": RECOVERY,
        "product": "lifetime",
        "status": "active",
        "token": TOKENS["LIFETIME"],
    }


def _not_found():
    return {"status": 404, "body": {"error": "license_not_found"}}


@pytest.fixture(autouse=True)
def _clean_premium():
    state.is_premium = False
    yield
    state.is_premium = False


@pytest.fixture
def fast_watcher(monkeypatch):
    from services import premium_service

    monkeypatch.setattr(premium_service, "CHECKOUT_WATCH_INTERVAL", 0.005)
    monkeypatch.setattr(premium_service, "CHECKOUT_WATCH_TIMEOUT", 0.5)


# -- checkout watcher -------------------------------------------------------


@pytest.mark.asyncio
async def test_watcher_polls_pending_then_unlocks_and_notifies(
    fast_watcher, monkeypatch
):
    from unittest import mock

    from services import kiri_license

    store = {}
    dbm = _dbm(store)
    urls = []
    script = [_not_found(), _not_found(), {"body": _active_body()}]
    premium = _service()
    with (
        mock.patch.object(
            kiri_license, "get_http_client", return_value=_http(script, urls)
        ),
        mock.patch.object(kiri_license, "db_manager", dbm),
        mock.patch("services.premium_service.notify") as notify,
    ):
        await premium._checkout_watch_loop(RECOVERY)

    assert len(urls) == 3, f"watcher should poll until confirmed, got {urls}"
    assert state.is_premium is True
    assert store.get("kiri_token") == TOKENS["LIFETIME"]
    notify.assert_called_once()
    assert "Premium unlocked" in notify.call_args[0][0]
    assert premium.license.unlocked is True


@pytest.mark.asyncio
async def test_watcher_gives_up_after_the_window_without_unlocking(
    fast_watcher, monkeypatch
):
    from unittest import mock

    # Shorter window than the deadline allows: every poll is "not found".
    from services import kiri_license, premium_service

    monkeypatch.setattr(premium_service, "CHECKOUT_WATCH_TIMEOUT", 0.02)
    premium = _service()
    urls = []
    with (
        mock.patch.object(
            kiri_license,
            "get_http_client",
            return_value=_http([_not_found()] * 50, urls),
        ),
        mock.patch.object(kiri_license, "db_manager", _dbm()),
        mock.patch("services.premium_service.notify") as notify,
    ):
        await premium._checkout_watch_loop(RECOVERY)

    assert state.is_premium is False
    notify.assert_not_called()
    assert len(urls) >= 1


@pytest.mark.asyncio
async def test_checkout_watcher_starts_with_the_checkout_and_double_start_is_safe():
    page = _TaskPage()
    premium = _service(page)
    premium.start_checkout_watch(RECOVERY)
    premium.start_checkout_watch(RECOVERY)
    assert len(page.tasks) == 2
    await asyncio.sleep(0)  # let the cancel propagate
    assert page.tasks[0].cancelled(), "a second checkout must stop the first watcher"
    assert not page.tasks[1].cancelled()
    premium.shutdown()
    await asyncio.sleep(0)
    assert page.tasks[1].cancelled(), "shutdown must cancel the live watcher"


@pytest.mark.asyncio
async def test_play_build_never_starts_any_watcher(monkeypatch):
    from unittest import mock

    monkeypatch.setattr("core.channel.CHANNEL", "play")
    monkeypatch.setattr("services.premium_service.CHANNEL", "play")
    page = mock.MagicMock()
    premium = PremiumService(page)
    premium.start_checkout_watch(RECOVERY)
    premium.start_reconcile_loop()
    await premium.reconcile()
    await premium.reconcile_if_due()
    page.run_task.assert_not_called()


# -- reconciler (renewal re-arm) -------------------------------------------


@pytest.mark.asyncio
async def test_reconcile_uses_the_token_issuing_path_and_re_arms_renewals():
    from unittest import mock

    from services import kiri_license

    store = {"kiri_recovery_id": RECOVERY}
    dbm = _dbm(store)
    urls = []
    script = [{"body": _active_body()}]
    premium = _service()
    # The post-renewal launch state: old token rejected/expired, claims gone.
    premium.license._unlocked = False
    premium.license.claims = None

    with (
        mock.patch.object(
            kiri_license, "get_http_client", return_value=_http(script, urls)
        ),
        mock.patch.object(kiri_license, "db_manager", dbm),
    ):
        await premium.reconcile()

    assert urls, "reconcile must talk to the Worker"
    assert urls[0].endswith("/restore"), (
        "reconcile must use the token-issuing path — a status-only reply "
        "leaves the old token to expire and locks a paying subscriber out"
    )
    assert premium.license.unlocked is True
    assert state.is_premium is True
    assert premium.license.claims is not None
    assert premium.license.claims.product == "lifetime"


@pytest.mark.asyncio
async def test_reconcile_without_a_recovery_id_makes_no_request():
    from unittest import mock

    from services import kiri_license

    dbm = _dbm({})  # nothing ever purchased
    urls = []
    premium = _service()
    with (
        mock.patch.object(
            kiri_license, "get_http_client", return_value=_http([_not_found()], urls)
        ),
        mock.patch.object(kiri_license, "db_manager", dbm),
    ):
        await premium.reconcile()
    assert urls == []


@pytest.mark.asyncio
async def test_resume_reconcile_debounces_bursts():
    from unittest import mock

    from services import kiri_license

    store = {"kiri_recovery_id": RECOVERY}
    dbm = _dbm(store)
    urls = []
    premium = _service()
    with (
        mock.patch.object(
            kiri_license,
            "get_http_client",
            return_value=_http([{"body": _active_body()}], urls),
        ),
        mock.patch.object(kiri_license, "db_manager", dbm),
    ):
        # Just reconciled (startup) — a resume burst must not re-hit the Worker.
        premium._last_reconcile_at = time.monotonic()
        await premium.reconcile_if_due()
        assert urls == []
        # Well past the debounce — the hourly loop / a real resume checks.
        premium._last_reconcile_at = time.monotonic() - 9999
        await premium.reconcile_if_due()
        assert len(urls) == 1


@pytest.mark.asyncio
async def test_hourly_loop_runs_until_shutdown():
    page = _TaskPage()
    premium = _service(page)
    premium.start_reconcile_loop()
    assert len(page.tasks) == 1
    premium.shutdown()
    await asyncio.sleep(0)
    assert page.tasks[0].cancelled()
    # A second start after shutdown is a fresh task, not a resurrection bug.
    premium.start_reconcile_loop()
    assert len(page.tasks) == 2
    premium.shutdown()
    await asyncio.sleep(0)
    assert page.tasks[1].cancelled()


# -- settings copy ----------------------------------------------------------


def test_premium_subtitle_is_honest_about_renewal():
    from unittest import mock

    from screens.settings_screen import _premium_subtitle

    pack = (
        "the premium channel pack: the top channels in every field "
        "and more country support"
    )

    # Free, phone (ads exist): both benefits, in the owner's wording.
    assert (
        _premium_subtitle(False, None, has_ads=True)
        == f"Remove all ads and unlock {pack}"
    )
    # Free, Android TV / desktop (no ads ever): never claim "no ads".
    assert _premium_subtitle(False, None, has_ads=False) == f"Unlock {pack}"

    claims = mock.Mock()
    claims.paid_through = 1793009434726  # 26 Oct 2026 UTC
    claims.product = "monthly"
    assert _premium_subtitle(True, claims, has_ads=True) == (
        "Ads removed · premium channels unlocked · "
        "active until 26 Oct 2026 · renews monthly"
    )
    assert _premium_subtitle(True, claims, has_ads=False) == (
        "Premium channels unlocked · active until 26 Oct 2026 · renews monthly"
    )

    claims.product = "yearly"
    assert "renews yearly" in _premium_subtitle(True, claims, has_ads=True)

    lifetime = mock.Mock()
    lifetime.paid_through = None
    lifetime.product = "lifetime"
    assert _premium_subtitle(True, lifetime, has_ads=True) == (
        "Ads removed · premium channels unlocked · thank you!"
    )
    assert _premium_subtitle(True, lifetime, has_ads=False) == (
        "Premium channels unlocked · thank you!"
    )
