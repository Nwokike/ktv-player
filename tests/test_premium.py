"""Tests for premium (remove-ads) gating.

Premium is a single backend now — the Kiri License Worker — so the store
side has no Play Billing path to cover; see test_kiri_license.py for the
entitlement itself. What belongs here is the promise the product makes:
a paying user never sees an ad.
"""

import inspect

import pytest

from components.banner_ad import build_banner_ad
from core.state import state
from screens.settings_screen import SettingsScreen
from services.ad_service import AdService


@pytest.fixture(autouse=True)
def _clean_state():
    state.reset()
    yield
    state.reset()


def _with_platform(page, mobile: bool = True):
    from types import SimpleNamespace

    page.platform = SimpleNamespace(is_mobile=lambda: mobile)
    return page


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
    assert build_banner_ad(fake_page).width == 0

    state.is_premium = False
    assert build_banner_ad(fake_page).width != 0


def test_build_banner_ad_hidden_on_desktop(fake_page):
    _with_platform(fake_page, mobile=False)
    state.is_premium = False
    assert build_banner_ad(fake_page).width == 0


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


# ── The Settings card ────────────────────────────────────────────────────


def test_settings_screen_has_premium_section():
    source = inspect.getsource(SettingsScreen)
    assert '"Premium"' in source
    assert "WORKSPACE_PREMIUM" in source
    assert "_kiri_checkout" in source or "_ask_email" in source
    assert "controls.append(premium)" in source


def test_premium_service_carries_no_billing():
    """Play Billing is gone with the extension; only Kiri remains."""
    import ast
    from pathlib import Path

    for rel in ("src/services/premium_service.py", "src/screens/settings_screen.py"):
        source = (Path(__file__).parent.parent / rel).read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in getattr(node, "names", [])]
                mod = getattr(node, "module", "") or ""
                assert not any(
                    "flet_billing" in n or "flet_ima" in n or mod == n for n in names
                ), f"{rel} still imports a removed extension"
        assert "flet_billing" not in source
        assert "flet_ima" not in source
