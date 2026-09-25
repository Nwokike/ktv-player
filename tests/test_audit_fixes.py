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
