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
