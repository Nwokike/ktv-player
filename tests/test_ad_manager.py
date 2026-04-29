import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import flet as ft
from services.ad_service import AdManager


@pytest.fixture
def mock_page():
    page = MagicMock(spec=ft.Page)
    page.platform = ft.PagePlatform.ANDROID
    page.overlay = []
    page.update = MagicMock()
    return page


@pytest.mark.asyncio
async def test_ad_manager_platform_ids(mock_page):
    ad_manager = AdManager(mock_page)

    # Android
    assert ad_manager.get_banner_unit_id() == AdManager.ANDROID_BANNER
    assert ad_manager.get_interstitial_unit_id() == AdManager.ANDROID_INTERSTITIAL

    # iOS
    mock_page.platform = ft.PagePlatform.IOS
    assert ad_manager.get_banner_unit_id() == AdManager.IOS_BANNER
    assert ad_manager.get_interstitial_unit_id() == AdManager.IOS_INTERSTITIAL


@pytest.mark.asyncio
async def test_interstitial_preloading(mock_page):
    ad_manager = AdManager(mock_page)
    await ad_manager.preload_interstitial()

    assert len(mock_page.overlay) == 1
    assert ad_manager.interstitial is not None
    mock_page.update.assert_called()


@pytest.mark.asyncio
async def test_banner_creation(mock_page):
    ad_manager = AdManager(mock_page)
    banner = ad_manager.create_banner()
    assert banner.unit_id == AdManager.ANDROID_BANNER


@pytest.mark.asyncio
async def test_show_interstitial(mock_page):
    ad_manager = AdManager(mock_page)
    # Preload first
    await ad_manager.preload_interstitial()

    # Mock the flet_ads.Interstitial object
    ad_manager.interstitial.show = MagicMock()

    await ad_manager.show_interstitial()
    ad_manager.interstitial.show.assert_called_once()


@pytest.mark.asyncio
async def test_show_interstitial_without_preloading(mock_page):
    ad_manager = AdManager(mock_page)
    # Should not crash, just return
    await ad_manager.show_interstitial()
    assert ad_manager.interstitial is None


@pytest.mark.asyncio
async def test_unsupported_platform(mock_page):
    mock_page.platform = ft.PagePlatform.WINDOWS
    ad_manager = AdManager(mock_page)
    # Current implementation falls back to Android unit IDs for other platforms
    assert ad_manager.get_banner_unit_id() == AdManager.ANDROID_BANNER
    assert ad_manager.get_interstitial_unit_id() == AdManager.ANDROID_INTERSTITIAL


@pytest.mark.asyncio
async def test_handle_close(mock_page):
    ad_manager = AdManager(mock_page)
    on_close = AsyncMock()
    await ad_manager.preload_interstitial(on_close=on_close)

    # Simulate close
    await ad_manager._handle_close(None)
    on_close.assert_called_once()
    # Should preload again
    assert mock_page.update.call_count >= 2


@pytest.mark.asyncio
async def test_preload_error(mock_page):
    with patch("flet_ads.InterstitialAd", side_effect=Exception("Failed")):
        ad_manager = AdManager(mock_page)
        await ad_manager.preload_interstitial()
        assert ad_manager.interstitial is None


@pytest.mark.asyncio
async def test_show_error(mock_page):
    ad_manager = AdManager(mock_page)
    ad_manager.interstitial = MagicMock()
    ad_manager.interstitial.show = AsyncMock(side_effect=Exception("Failed"))

    result = await ad_manager.show_interstitial()
    assert result is False
