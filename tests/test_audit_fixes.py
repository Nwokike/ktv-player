"""Regressions found by the unbiased 2.1.0-vs-now comparison.

Each test pins one defect the audit found after the player/ads were
restored, so the fixes cannot be quietly undone.
"""

import inspect
from unittest import mock

import pytest

from core.state import state
from services.kiri_license import LicenseUnavailable
from tests.license_fixtures import PUBLIC_KEY, TOKENS


@pytest.fixture(autouse=True)
def _clean_state():
    state.reset()
    yield
    state.reset()


@pytest.fixture
def store():
    """In-memory settings table for the license service."""
    values: dict[str, str] = {}

    async def get_setting(key, default=None):
        return values.get(key, default)

    async def set_setting(key, value):
        values[key] = str(value)

    dbm = mock.AsyncMock()
    dbm.get_setting.side_effect = get_setting
    dbm.set_setting.side_effect = set_setting
    with mock.patch("services.kiri_license.db_manager", dbm):
        yield values


# 1. The Restore button passed an event to a zero-argument handler, which
#    raised TypeError the moment it was tapped on a direct build.
def test_settings_restore_handlers_accept_an_event():
    from screens.settings_screen import SettingsScreen

    source = inspect.getsource(SettingsScreen)
    assert "def _ask_recovery_id(e=None):" in source, (
        "Flet invokes on_click with an event — a zero-arg handler crashes "
        "the direct-build Restore button with a TypeError"
    )


# 2. reconcile() returned early while unlocked, so a refunded or revoked
#    license never came back. The Worker is authoritative when online.
@pytest.mark.asyncio
async def test_reconcile_refreshes_an_unlocked_license():
    from services.kiri_license import KiriLicenseService
    from services.premium_service import PremiumService

    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    svc._unlocked = True  # standing unlock, as load_local left it
    svc.on_change = lambda: None

    dbm = mock.AsyncMock()
    dbm.get_setting.return_value = "KIRI-L-abc"

    refreshed = {"calls": 0}

    class _Resp:
        status_code = 200

        def json(self):
            refreshed["calls"] += 1
            return {
                "recovery_id": "KIRI-L-x",
                "product": "lifetime",
                "status": "active",
            }

    async def post(*args, **kwargs):
        return _Resp()

    premium = PremiumService(mock.MagicMock())
    premium.license = svc
    with (
        mock.patch("services.kiri_license.get_http_client") as http,
        mock.patch("services.kiri_license.db_manager", dbm),
    ):
        http.return_value.post = post
        await premium.reconcile()

    assert refreshed["calls"] == 1, "an unlocked license was never re-checked"


# 3. A token the Worker rejects must drop a standing unlock, not keep it.
@pytest.mark.asyncio
async def test_a_rejected_token_drops_a_standing_unlock():
    from services.kiri_license import KiriLicenseService

    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    svc._unlocked = True
    svc.claims = None

    body = {
        "recovery_id": "KIRI-L-x",
        "product": "lifetime",
        "status": "active",
        "token": TOKENS["WRONG_APP"],
    }
    response = mock.Mock()
    response.status_code = 200
    response.json.return_value = body

    async def post(*args, **kwargs):
        return response

    client = mock.Mock()
    client.post = post

    # return_value is the shape that works throughout this suite: the
    # patched get_http_client() then returns the client below.
    with (
        mock.patch(
            "services.kiri_license.get_http_client",
            return_value=client,
        ),
        pytest.raises(LicenseUnavailable),
    ):
        await svc.restore("KIRI-L-x")

    assert svc.unlocked is False, "a bad token left the previous unlock in place"
    # ...and the app-wide flag must follow, or ads return while licensed.
    from services.premium_service import PremiumService

    premium = PremiumService(mock.MagicMock())
    premium.license = svc
    svc.on_change = premium._recompute_premium
    premium._recompute_premium()
    assert state.is_premium is False


# 4. Back on a pushed overlay (recently-watched) must pop it, not exit.
def test_back_on_an_overlay_view_pops_it():
    from src.main import AppController

    controller = AppController(_FakePage())
    controller.page.views = [_FakeView("/"), _FakeView("/recently-watched")]

    controller.view_pop(mock.MagicMock())

    routes = [v.route for v in controller.page.views]
    assert routes == ["/"], f"overlay was not popped: {routes}"


# 5. A failed existence query is not proof of deletion.
def test_media_store_exists_never_fakes_a_delete():
    from services.local_scanner import media_store_exists

    # No JVM off-device: the helper must answer "unknown" (None) rather
    # than False, which callers read as "the row is gone".
    assert media_store_exists("content://media/external/video/media/1") is None
    assert media_store_exists("") is False


class _FakeView:
    def __init__(self, route):
        self.route = route
        self.controls = []


class _FakePage:
    def __init__(self):
        self.views = []
        self.route = "/"
        self.platform = SimplePlatform()
        self.services = []

    def update(self):
        pass

    def run_task(self, fn, *args, **kwargs):
        return None


class SimplePlatform:
    def is_mobile(self):
        return True


# 7. An authoritative refusal from the Worker must drop premium, not keep
#    it. Only a transport failure may preserve the local verdict.
@pytest.mark.asyncio
async def test_an_http_refusal_drops_premium():
    from services.kiri_license import KiriLicenseService
    from services.premium_service import PremiumService

    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    svc._unlocked = True

    response = mock.Mock()
    response.status_code = 404
    response.json.return_value = {"message": "license_not_found"}

    async def post(*args, **kwargs):
        return response

    client = mock.Mock()
    client.post = post

    premium = PremiumService(mock.MagicMock())
    premium.license = svc
    dbm = mock.AsyncMock()
    dbm.get_setting.return_value = "KIRI-L-abc"
    with (
        mock.patch("services.kiri_license.get_http_client", return_value=client),
        mock.patch("services.kiri_license.db_manager", dbm),
    ):
        await premium.reconcile()

    assert svc.unlocked is False
    assert state.is_premium is False, "a 404 from the Worker kept premium"


# 8. A token returned with a revoked status must not be cached — next boot
#    would verify it and re-unlock.
@pytest.mark.asyncio
async def test_a_revoked_status_does_not_persist_the_token(store):
    from services.kiri_license import KiriLicenseService

    svc = KiriLicenseService(public_key=PUBLIC_KEY, on_change=lambda: None)
    body = {
        "recovery_id": "KIRI-L-x",
        "product": "lifetime",
        "status": "revoked",
        "token": TOKENS["LIFETIME"],
    }
    response = mock.Mock()
    response.status_code = 200
    response.json.return_value = body

    async def post(*args, **kwargs):
        return response

    client = mock.Mock()
    client.post = post
    with mock.patch("services.kiri_license.get_http_client", return_value=client):
        status = await svc.restore("KIRI-L-x")

    assert status.unlocks is False
    assert svc.unlocked is False
    assert store.get("kiri_token") in ("", None), (
        "a revoked license left a verifiable token behind for next boot"
    )


# 9. The refusal classifier must not treat a throttle as a revocation.
def test_rate_limit_is_not_a_refusal():
    from services.kiri_license import status_refusal

    assert status_refusal(403) is True
    assert status_refusal(404) is True
    assert status_refusal(429) is False, "a throttled check must not revoke"
    assert status_refusal(500) is False, "a server fault is transport"
