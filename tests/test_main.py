import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import flet as ft
from main import main
import base64
import asyncio

@pytest.fixture
def mock_page():
    page = MagicMock(spec=ft.Page)
    page.session = MagicMock()
    page.views = []
    page.overlay = []
    page.theme = MagicMock()
    page.dark_theme = MagicMock()
    page.update = MagicMock()
    page.run_task = MagicMock()
    page.push_route = AsyncMock()
    page.route = "/" # Initialize with a string
    return page

@pytest.mark.asyncio
async def test_main_init(mock_page):
    with patch('database.manager.db_manager.init_db', new_callable=AsyncMock) as mock_init_db, \
         patch('database.manager.db_manager.get_setting', new_callable=AsyncMock) as mock_get_setting:
        
        mock_get_setting.side_effect = lambda k, d: "true" if k == "has_accepted_terms" else d
        
        await main(mock_page)
        
        mock_init_db.assert_called_once()
        assert mock_page.title == "KTV Player"
        mock_page.update.assert_called()

@pytest.mark.asyncio
async def test_navigation_dashboard(mock_page):
    with patch('database.manager.db_manager.init_db', new_callable=AsyncMock), \
         patch('database.manager.db_manager.get_setting', new_callable=AsyncMock) as mock_get_setting:
        
        mock_get_setting.side_effect = lambda k, d: "true" if k == "has_accepted_terms" else d
        
        await main(mock_page)
        
        # Simulate route change to /dashboard
        mock_page.route = "/dashboard"
        route_change_handler = mock_page.on_route_change
        await route_change_handler(None)
        
        assert any(v.route == "/dashboard" for v in mock_page.views)

@pytest.mark.asyncio
async def test_navigation_onboarding(mock_page):
    with patch('database.manager.db_manager.init_db', new_callable=AsyncMock), \
         patch('database.manager.db_manager.get_setting', new_callable=AsyncMock) as mock_get_setting:
        
        mock_get_setting.side_effect = lambda k, d: "false" if k == "has_accepted_terms" else d
        
        await main(mock_page)
        
        mock_page.route = "/onboarding"
        route_change_handler = mock_page.on_route_change
        await route_change_handler(None)
        
        assert any(v.route == "/onboarding" for v in mock_page.views)

@pytest.mark.asyncio
async def test_navigation_play(mock_page):
    with patch('database.manager.db_manager.init_db', new_callable=AsyncMock), \
         patch('database.manager.db_manager.get_setting', new_callable=AsyncMock):
        
        await main(mock_page)
        
        url = "http://example.com/stream.m3u8"
        encoded_url = base64.urlsafe_b64encode(url.encode()).decode()
        mock_page.route = f"/play?url={encoded_url}"
        
        route_change_handler = mock_page.on_route_change
        await route_change_handler(None)
        
        assert any(v.route.startswith("/play") for v in mock_page.views)

@pytest.mark.asyncio
async def test_view_pop(mock_page):
    with patch('database.manager.db_manager.init_db', new_callable=AsyncMock), \
         patch('database.manager.db_manager.get_setting', new_callable=AsyncMock):
        
        await main(mock_page)
        
        # Setup views
        play_view = MagicMock(spec=ft.View)
        play_view.route = "/play?url=abc"
        play_view.controls = []
        
        dash_view = MagicMock(spec=ft.View)
        dash_view.route = "/dashboard"
        
        mock_page.views = [dash_view, play_view]
        
        view_pop_handler = mock_page.on_view_pop
        view_pop_handler(None)
        
        assert len(mock_page.views) == 1
        mock_page.run_task.assert_called()

@pytest.mark.asyncio
async def test_error_handler(mock_page):
    with patch('database.manager.db_manager.init_db', new_callable=AsyncMock), \
         patch('database.manager.db_manager.get_setting', new_callable=AsyncMock):
        
        await main(mock_page)
        
        error_handler = mock_page.on_error
        mock_error = MagicMock()
        mock_error.data = "Test Error"
        error_handler(mock_error)
        
        assert mock_page.snack_bar is not None
        mock_page.update.assert_called()
