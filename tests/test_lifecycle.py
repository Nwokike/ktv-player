import pytest
from unittest.mock import MagicMock, AsyncMock
import flet as ft
from services.lifecycle import LifecycleManager
from core.state import state

@pytest.fixture
def mock_page():
    page = MagicMock(spec=ft.Page)
    page.update = MagicMock()
    page.update_async = AsyncMock()
    return page

@pytest.mark.asyncio
async def test_lifecycle_init(mock_page):
    manager = LifecycleManager(mock_page)
    assert mock_page.on_app_lifecycle_state_change == manager._handle_lifecycle_change

@pytest.mark.asyncio
async def test_lifecycle_pause(mock_page):
    manager = LifecycleManager(mock_page)
    event = MagicMock(spec=ft.AppLifecycleStateChangeEvent)
    event.state = "pause"
    
    state.is_loading = True
    await manager._handle_lifecycle_change(event)
    
    assert state.is_loading is False
    mock_page.update.assert_called_once()

@pytest.mark.asyncio
async def test_lifecycle_resume(mock_page):
    manager = LifecycleManager(mock_page)
    event = MagicMock(spec=ft.AppLifecycleStateChangeEvent)
    event.state = "resume"
    
    await manager._handle_lifecycle_change(event)
    mock_page.update.assert_called_once()

@pytest.mark.asyncio
async def test_lifecycle_data_fallback(mock_page):
    # Test fallback to e.data if e.state is missing
    manager = LifecycleManager(mock_page)
    event = MagicMock()
    del event.state
    event.data = "pause"
    
    state.is_loading = True
    await manager._handle_lifecycle_change(event)
    assert state.is_loading is False

@pytest.mark.asyncio
async def test_lifecycle_async_update(mock_page):
    # Test async update path
    mock_page.update = AsyncMock() # Make it a coroutine
    manager = LifecycleManager(mock_page)
    event = MagicMock(spec=ft.AppLifecycleStateChangeEvent)
    event.state = "resume"
    
    await manager._handle_lifecycle_change(event)
    mock_page.update_async.assert_called_once()
