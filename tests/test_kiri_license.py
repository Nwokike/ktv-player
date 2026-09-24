"""Kiri License client and PremiumService backend selection.

These cover the path that makes premium work where Play cannot: a
sideloaded APK, the Windows build, Linux. Play Billing only accepts
Play-installed builds and linked license testers, so the Worker is not a
fallback for convenience — it is the only working checkout on those
surfaces.
"""

from types import SimpleNamespace
from unittest import mock

import pytest

from core.state import state
from services.kiri_license import (
    KiriLicenseService,
    LicenseProduct,
    LicenseUnavailable,
)
from services.premium_service import PremiumService
from tests.license_fixtures import PUBLIC_KEY, TOKENS

APP = "ng.kiri.ktvplayer"


@pytest.fixture(autouse=True)
def _clean_state():
    state.reset()
    yield
    state.reset()


@pytest.fixture
def store():
    """In-memory stand-in for the settings table."""
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


def _response(json_body, status_code=200):
    response = mock.Mock()
    response.status_code = status_code
    response.json.return_value = json_body
    response.raise_for_status.return_value = None
    return response


def _http(method: str, response, recorder: list):
    async def call(*args, **kwargs):
        recorder.append((args, kwargs))
        return response

    return mock.Mock(**{method: call})


# -- catalog ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_catalog_parses_products_and_prices(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    body = {
        "products": [
            {
                "id": "lifetime",
                "amount": 49.99,
                "currency": "USD",
                "kind": "one_time",
                "description": "Lifetime access",
            },
            {
                "id": "monthly",
                "amount": 3.99,
                "currency": "USD",
                "kind": "recurring",
                "description": "Monthly access",
            },
        ]
    }
    calls: list = []
    with mock.patch(
        "services.kiri_license.get_http_client",
        return_value=_http("get", _response(body), calls),
    ):
        products = await svc.fetch_catalog()

    assert [p.id for p in products] == ["lifetime", "monthly"]
    assert products[0].price_label == "$49.99 USD"
    assert products[1].price_label == "$3.99 USD"
    assert calls[0][0][0].endswith("/catalog")


@pytest.mark.asyncio
async def test_catalog_is_cached_between_calls(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    body = {"products": [{"id": "lifetime", "amount": 49.99, "currency": "USD"}]}
    calls: list = []
    with mock.patch(
        "services.kiri_license.get_http_client",
        return_value=_http("get", _response(body), calls),
    ):
        await svc.fetch_catalog()
        await svc.fetch_catalog()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_catalog_failure_is_explicit(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    with (
        mock.patch(
            "services.kiri_license.get_http_client",
            side_effect=RuntimeError("no network"),
        ),
        pytest.raises(LicenseUnavailable),
    ):
        await svc.fetch_catalog()


def test_price_label_handles_other_currencies():
    assert LicenseProduct("x", 1500, "NGN", "one_time", "").price_label == "₦1,500 NGN"
    assert LicenseProduct("x", 9.5, "EUR", "one_time", "").price_label == "€9.5 EUR"


# -- checkout ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkout_posts_the_app_and_product_and_saves_recovery_id(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    body = {
        "recovery_id": "KIRI-L-abc123",
        "checkout_url": "https://checkout.flutterwave.com/x",
        "product": "lifetime",
        "amount": 49.99,
        "currency": "USD",
    }
    calls: list = []
    with mock.patch(
        "services.kiri_license.get_http_client",
        return_value=_http("post", _response(body, 201), calls),
    ):
        checkout = await svc.checkout("lifetime", "buyer@example.com")

    assert checkout.recovery_id == "KIRI-L-abc123"
    assert checkout.checkout_url.startswith("https://")
    # The recovery ID is the only way back in after a data wipe, so it is
    # persisted before the user ever leaves the app.
    assert store["kiri_recovery_id"] == "KIRI-L-abc123"
    payload = calls[0][1]["json"]
    assert payload["app_id"] == APP
    assert payload["product_id"] == "lifetime"
    assert payload["email"] == "buyer@example.com"


@pytest.mark.asyncio
async def test_checkout_reports_the_worker_message(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    with (
        mock.patch(
            "services.kiri_license.get_http_client",
            return_value=_http(
                "post", _response({"message": "email_required"}, 400), []
            ),
        ),
        pytest.raises(LicenseUnavailable) as caught,
    ):
        await svc.checkout("lifetime", "nope")
    assert "email_required" in str(caught.value)


@pytest.mark.asyncio
async def test_checkout_rejects_an_incomplete_order(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    with (
        mock.patch(
            "services.kiri_license.get_http_client",
            return_value=_http("post", _response({"recovery_id": ""}), []),
        ),
        pytest.raises(LicenseUnavailable),
    ):
        await svc.checkout("lifetime", "buyer@example.com")


# -- restore / offline token ------------------------------------------------


def _restore_body(status="active", token=TOKENS["LIFETIME"]):
    body = {
        "recovery_id": "KIRI-L-abc123",
        "product": "lifetime",
        "status": status,
        "scope": "universal",
    }
    if token is not None:
        body["token"] = token
    return body


@pytest.mark.asyncio
async def test_restore_with_a_verified_token_unlocks_premium(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    with mock.patch(
        "services.kiri_license.get_http_client",
        return_value=_http("post", _response(_restore_body()), []),
    ):
        status = await svc.restore("KIRI-L-abc123")

    assert status.unlocks is True
    assert state.is_premium is True
    assert store["kiri_token"] == TOKENS["LIFETIME"]


@pytest.mark.asyncio
async def test_restore_refuses_a_token_signed_for_another_app(store):
    """An active license for someone else's app must not unlock this one."""
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    with (
        mock.patch(
            "services.kiri_license.get_http_client",
            return_value=_http(
                "post", _response(_restore_body(token=TOKENS["WRONG_APP"])), []
            ),
        ),
        pytest.raises(LicenseUnavailable),
    ):
        await svc.restore("KIRI-L-abc123")
    assert state.is_premium is False


@pytest.mark.asyncio
async def test_restore_of_a_revoked_license_does_not_unlock(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    with mock.patch(
        "services.kiri_license.get_http_client",
        return_value=_http(
            "post", _response(_restore_body(status="revoked", token=None)), []
        ),
    ):
        status = await svc.restore("KIRI-L-abc123")
    assert status.unlocks is False
    assert state.is_premium is False


@pytest.mark.asyncio
async def test_cached_token_unlocks_without_a_network(store):
    store["kiri_token"] = TOKENS["LIFETIME"]
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    assert await svc.apply_cached_token() is True
    assert state.is_premium is True


@pytest.mark.asyncio
async def test_expired_cached_token_does_not_unlock(store):
    store["kiri_token"] = TOKENS["EXPIRED"]
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    assert await svc.apply_cached_token() is False
    assert state.is_premium is False


@pytest.mark.asyncio
async def test_no_cached_token_is_not_an_error(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    assert await svc.apply_cached_token() is False


@pytest.mark.asyncio
async def test_refresh_without_a_saved_license_is_a_no_op(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    assert await svc.refresh() is None


@pytest.mark.asyncio
async def test_restore_requires_a_recovery_id(store):
    svc = KiriLicenseService(public_key=PUBLIC_KEY)
    with pytest.raises(LicenseUnavailable):
        await svc.restore("   ")


# -- PremiumService backend selection ---------------------------------------


def _page(mobile: bool):
    page = mock.MagicMock()
    page.platform = SimpleNamespace(
        is_mobile=lambda: mobile,
        __eq__=lambda self, other: False,
    )
    page.services = []
    return page


def _premium_service(page, billing=None):
    with mock.patch("services.premium_service.Billing", return_value=billing):
        return PremiumService(page)


@pytest.mark.asyncio
async def test_desktop_falls_back_to_the_license_worker(store):
    svc = _premium_service(_page(mobile=False))
    assert svc.backend == "kiri"
    assert svc.uses_play is False
    # A purchase cannot be started without a browser flow on Kiri.
    assert await svc.buy() is False


@pytest.mark.asyncio
async def test_sideloaped_android_uses_kiri_until_play_proves_itself(store):
    billing = mock.MagicMock()
    billing.is_available = mock.AsyncMock(return_value=False)
    svc = _premium_service(_page(mobile=True), billing)

    await svc.reconcile()

    assert svc.backend == "kiri"
    assert svc.uses_play is False


@pytest.mark.asyncio
async def test_play_installed_switches_the_backend_to_play(store):
    billing = mock.MagicMock()
    billing.is_available = mock.AsyncMock(return_value=True)
    billing.query_products = mock.AsyncMock(
        return_value=SimpleNamespace(error=None, products=[])
    )
    billing.query_past_purchases = mock.AsyncMock(
        return_value=SimpleNamespace(purchases=[])
    )
    billing.restore_purchases = mock.AsyncMock(return_value=None)
    svc = _premium_service(_page(mobile=True), billing)

    await svc.reconcile()

    assert svc.backend == "play"
    assert svc.uses_play is True
    billing.restore_purchases.assert_awaited()


@pytest.mark.asyncio
async def test_cached_license_is_applied_on_the_boot_path(store):
    """Premium must survive a cold, offline start from the signed token."""
    store["kiri_token"] = TOKENS["LIFETIME"]
    dbm = mock.AsyncMock()

    async def get_setting(key, default=None):
        return store.get(key, default)

    async def set_setting(key, value):
        store[key] = str(value)

    dbm.get_setting.side_effect = get_setting
    dbm.set_setting.side_effect = set_setting

    svc = _premium_service(_page(mobile=False))
    svc.license.public_key = PUBLIC_KEY
    with mock.patch("services.premium_service.db_manager", dbm):
        await svc.load_local()

    assert state.is_premium is True
