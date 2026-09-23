"""Tests for premium (remove-ads) gating and PremiumService."""

import inspect
from types import SimpleNamespace
from unittest import mock

import pytest
from flet_billing import Billing, Purchase, PurchaseStatus

from components.banner_ad import build_banner_ad
from core.state import state
from screens.settings_screen import SettingsScreen
from services.ad_service import AdService
from services.premium_service import PREMIUM_PRODUCT_ID, PremiumService


@pytest.fixture(autouse=True)
def _clean_state():
    state.reset()
    yield
    state.reset()


def _with_platform(page, mobile: bool = True):
    page.platform = SimpleNamespace(is_mobile=lambda: mobile)
    return page


def _db(get_setting_return=None):
    dbm = mock.AsyncMock()
    dbm.get_setting.return_value = get_setting_return
    dbm.set_setting.return_value = None
    return dbm


# ── Ad gating: premium users see no ads ──────────────────────────────────


def test_banner_ad_getters_hidden_when_premium(fake_page):
    _with_platform(fake_page)
    svc = AdService(fake_page)

    state.is_premium = False
    assert svc.get_standard_banner_ad() is not None
    assert svc.get_anchor_banner_ad() is not None
    assert svc.get_native_style_ad() is not None

    state.is_premium = True
    assert svc.get_standard_banner_ad() is None
    assert svc.get_anchor_banner_ad() is None
    assert svc.get_native_style_ad() is None


def test_build_banner_ad_collapses_when_premium(fake_page):
    _with_platform(fake_page)

    state.is_premium = True
    collapsed = build_banner_ad(fake_page)
    assert collapsed.width == 0

    state.is_premium = False
    shown = build_banner_ad(fake_page)
    assert shown.width != 0


@pytest.mark.asyncio
async def test_preload_skipped_when_premium(fake_page):
    _with_platform(fake_page)
    svc = AdService(fake_page)
    state.is_premium = True

    await svc.preload_interstitial()

    assert svc.interstitial is None
    assert svc._ad_loaded_event is not None
    assert svc._ad_loaded_event.is_set()


@pytest.mark.asyncio
async def test_show_interstitial_blocked_when_premium(fake_page):
    _with_platform(fake_page)
    svc = AdService(fake_page)
    state.is_premium = True

    assert await svc.show_interstitial() is False


# ── PremiumService: boot restore, purchase events, persistence ───────────


@pytest.mark.asyncio
async def test_restore_reads_local_premium_flag(fake_page):
    dbm = _db(get_setting_return="true")
    with (
        mock.patch("services.premium_service.db_manager", dbm),
        mock.patch.object(Billing, "is_available", mock.AsyncMock(return_value=False)),
    ):
        svc = PremiumService(fake_page)
        await svc.restore()

    assert state.is_premium is True
    assert fake_page.services and isinstance(fake_page.services[0], Billing)


@pytest.mark.asyncio
async def test_restore_upgrades_from_owned_product(fake_page):
    dbm = _db(get_setting_return=None)
    owned = SimpleNamespace(
        purchases=[
            SimpleNamespace(
                product_id=PREMIUM_PRODUCT_ID,
                status=PurchaseStatus.PURCHASED,
            )
        ],
        error=None,
    )
    products = SimpleNamespace(
        products=[SimpleNamespace(price="$4.99")],
        not_found_ids=[],
        error=None,
    )
    with (
        mock.patch("services.premium_service.db_manager", dbm),
        mock.patch.object(Billing, "is_available", mock.AsyncMock(return_value=True)),
        mock.patch.object(
            Billing, "query_products", mock.AsyncMock(return_value=products)
        ),
        mock.patch.object(
            Billing, "query_past_purchases", mock.AsyncMock(return_value=owned)
        ),
        mock.patch.object(Billing, "restore_purchases", mock.AsyncMock()),
    ):
        svc = PremiumService(fake_page)
        await svc.restore()

    assert state.is_premium is True
    assert svc.price == "$4.99"
    dbm.set_setting.assert_awaited_with("premium", "true")


@pytest.mark.asyncio
async def test_restore_failure_keeps_local_flag(fake_page):
    dbm = _db(get_setting_return="true")
    with (
        mock.patch("services.premium_service.db_manager", dbm),
        mock.patch.object(
            Billing,
            "is_available",
            mock.AsyncMock(side_effect=RuntimeError("no session")),
        ),
    ):
        svc = PremiumService(fake_page)
        await svc.restore()

    assert state.is_premium is True


@pytest.mark.asyncio
async def test_purchase_event_activates_and_acknowledges(fake_page):
    dbm = _db()
    complete = mock.AsyncMock()
    with (
        mock.patch("services.premium_service.db_manager", dbm),
        mock.patch.object(Billing, "complete_purchase", complete),
    ):
        svc = PremiumService(fake_page)
        purchase = Purchase(
            status=PurchaseStatus.PURCHASED,
            product_id=PREMIUM_PRODUCT_ID,
            purchase_id="tx123",
            pending_complete_purchase=True,
        )
        await svc._on_purchases(SimpleNamespace(purchases=[purchase]))

    # The 3-day rule: acknowledge inside the event handler.
    complete.assert_awaited_once_with("tx123")
    assert state.is_premium is True
    dbm.set_setting.assert_awaited_with("premium", "true")


@pytest.mark.asyncio
async def test_other_products_do_not_activate(fake_page):
    dbm = _db()
    with mock.patch("services.premium_service.db_manager", dbm):
        svc = PremiumService(fake_page)
        purchase = Purchase(
            status=PurchaseStatus.PURCHASED,
            product_id="coins_100",
            purchase_id="x",
            pending_complete_purchase=False,
        )
        await svc._on_purchases(SimpleNamespace(purchases=[purchase]))

    assert state.is_premium is False


# ── Settings: Premium section present and wired (source contract) ────────


def test_settings_screen_has_premium_section():
    source = inspect.getsource(SettingsScreen)
    assert '"Premium"' in source
    assert "WORKSPACE_PREMIUM" in source
    assert "_buy_premium" in source
    assert "_restore_premium" in source
    assert "controls.append(premium)" in source
