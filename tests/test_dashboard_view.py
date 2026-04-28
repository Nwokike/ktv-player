import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import flet as ft
from views.dashboard import build_dashboard_view
from core.state import state

@pytest.fixture
def mock_page():
    page = MagicMock(spec=ft.Page)
    page.update = MagicMock()
    
    # Improved run_task to handle coroutines
    page._tasks = []
    async def run_task_mock(f, *args, **kwargs):
        if asyncio.iscoroutinefunction(f):
            return await f(*args, **kwargs)
        elif asyncio.iscoroutine(f):
            return await f
        else:
            return f(*args, **kwargs)
            
    def run_task_side_effect(f, *args, **kwargs):
        t = asyncio.create_task(run_task_mock(f, *args, **kwargs))
        page._tasks.append(t)
        return t
            
    page.run_task = MagicMock(side_effect=run_task_side_effect)
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    page.theme_mode = ft.ThemeMode.DARK
    return page

@pytest.fixture
def sample_channels():
    return [
        {"name": "BBC News", "url": "url1", "group": "UK; News", "country_code": "UK"},
        {"name": "CNN", "url": "url2", "group": "USA; News", "country_code": "USA"},
        {"name": "Custom 1", "url": "url3", "group": "Custom", "is_custom": True}
    ]

@pytest.mark.asyncio
async def test_dashboard_view_build(mock_page):
    on_play = MagicMock()
    state.channels = []
    view = build_dashboard_view(mock_page, on_play)
    assert isinstance(view, ft.View)
    assert view.route == "/dashboard"

@pytest.mark.asyncio
async def test_tab_switching(mock_page):
    on_play = MagicMock()
    view = build_dashboard_view(mock_page, on_play)
    
    # Find Tabs control
    main_col = view.controls[0].content.content
    tabs = next(c for c in main_col.controls if isinstance(c, ft.Tabs))
    
    # Simulate tab change to 'Categories' (index 1)
    event = MagicMock()
    event.data = "1"
    tabs.on_change(event)
    
    mock_page.update.assert_called()

@pytest.mark.asyncio
async def test_channel_search(mock_page, sample_channels):
    on_play = MagicMock()
    state.channels = sample_channels
    state.is_loading = False
    view = build_dashboard_view(mock_page, on_play)
    
    # Find SearchBar
    main_col = view.controls[0].content.content
    header = main_col.controls[0]
    search_bar = next(c for c in header.controls if isinstance(c, ft.SearchBar))
    
    # Simulate search
    with patch('asyncio.sleep', new_callable=AsyncMock): # Skip debounce sleep
        event = MagicMock()
        event.data = "BBC"
        search_bar.on_change(event)
        
    # Await the task that was scheduled
    for task in mock_page._tasks:
        await task
        
    # Verify content update
    mock_page.update.assert_called()

@pytest.mark.asyncio
async def test_add_custom_content_dialog(mock_page):
    on_play = MagicMock()
    view = build_dashboard_view(mock_page, on_play)
    
    # Find the "Add Custom Configuration" button in Custom tab
    main_col = view.controls[0].content.content
    tabs = next(c for c in main_col.controls if isinstance(c, ft.Tabs))
    event = MagicMock()
    event.data = "2"
    tabs.on_change(event)
    
    # Find the button in the Custom tab content
    tab_view_container = tabs.content.controls[1]
    custom_tab_content = tab_view_container.controls[2] 
    add_button = next(c for c in custom_tab_content.controls if isinstance(c, ft.FilledButton))
    
    # Simulate click
    add_button.on_click(MagicMock())
    mock_page.show_dialog.assert_called_once()

@pytest.mark.asyncio
async def test_clear_data_actions(mock_page):
    on_play = MagicMock()
    view = build_dashboard_view(mock_page, on_play)
    
    # Switch to Settings tab (index 3)
    main_col = view.controls[0].content.content
    tabs = next(c for c in main_col.controls if isinstance(c, ft.Tabs))
    tabs.on_change(MagicMock(data="3"))
    
    tab_view_container = tabs.content.controls[1]
    settings_content = tab_view_container.controls[3] 
    settings_col = settings_content.controls[0]
    
    # Find clear history tile
    clear_history_tile = next(c for c in settings_col.controls if isinstance(c, ft.ListTile) and "History" in c.title.value)
    
    with patch('database.manager.db_manager.clear_history', new_callable=AsyncMock) as mock_clear:
        await clear_history_tile.on_click(MagicMock())
        mock_clear.assert_called_once()

@pytest.mark.asyncio
async def test_theme_toggle(mock_page):
    on_play = MagicMock()
    view = build_dashboard_view(mock_page, on_play)
    
    main_col = view.controls[0].content.content
    header = main_col.controls[0]
    theme_button = next(c for c in header.controls if isinstance(c, ft.IconButton))
    
    initial_theme = mock_page.theme_mode
    theme_button.on_click(MagicMock())
    
    assert mock_page.theme_mode != initial_theme
    assert state.theme_mode == mock_page.theme_mode
    mock_page.update.assert_called()

@pytest.mark.asyncio
async def test_channel_card_click(mock_page, sample_channels):
    on_play = AsyncMock()
    state.channels = sample_channels
    state.is_loading = False
    view = build_dashboard_view(mock_page, on_play)
    
    # Trigger content build for countries
    main_col = view.controls[0].content.content
    tabs = next(c for c in main_col.controls if isinstance(c, ft.Tabs))
    
    # Tab 0 is countries
    tabs.on_change(MagicMock(data="0"))
    
    tab_view_container = tabs.content.controls[1]
    countries_content = tab_view_container.controls[0]
    
    # Find the ResponsiveRow (grid)
    # countries_content is a ListView, its controls should contain the grid
    grid = next(c for c in countries_content.controls if isinstance(c, ft.ResponsiveRow))
    card = grid.controls[0] # The Container wrapper
    
    # Click the card
    await card.on_click(MagicMock())
    
    # Verify run_task was called with on_play and url
    mock_page.run_task.assert_called()
    found = False
    for call in mock_page.run_task.call_args_list:
        if call[0][0] == on_play and call[0][1] == sample_channels[0]["url"]:
            found = True
            break
    assert found
