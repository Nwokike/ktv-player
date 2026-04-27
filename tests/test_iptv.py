import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.iptv_service import IPTVService
import os

@pytest.fixture
def iptv_service():
    return IPTVService()

@pytest.mark.asyncio
async def test_fetch_built_in_channels(iptv_service):
    with patch('channels.provider.channel_provider.get_all_channels') as mock_get:
        mock_get.return_value = []
        channels = await iptv_service.fetch_built_in_channels()
        assert isinstance(channels, list)
        assert len(channels) == 0

@pytest.mark.asyncio
async def test_load_all_sources(iptv_service):
    # Mocking both built-in and external sources
    with patch.object(iptv_service, 'fetch_built_in_channels', new_callable=AsyncMock) as mock_built_in:
        mock_built_in.return_value = [{"name": "Built-in", "url": "url1"}]
        
        with patch.object(iptv_service, 'fetch_playlist', new_callable=AsyncMock) as mock_ext:
            mock_ext.return_value = [{"name": "External", "url": "url2"}]
            
            with patch('database.manager.db_manager.get_playlists', new_callable=AsyncMock) as mock_db_p:
                mock_db_p.return_value = [{"name": "Custom Playlist", "url": "url3", "is_active": 1}]
                
                with patch('database.manager.db_manager.get_custom_channels', new_callable=AsyncMock) as mock_db_c:
                    mock_db_c.return_value = [{"name": "Single Channel", "url": "url4", "group": "Custom"}]
                    
                    all_channels = await iptv_service.load_all_sources()
                    
                    # 1 built-in, 1 custom playlist (returns 1), 1 custom channel = 3
                    assert len(all_channels) == 3
                    assert all_channels[0]["name"] == "Built-in"
                    assert all_channels[-1]["name"] == "Single Channel"

@pytest.mark.asyncio
async def test_fetch_playlist_error_handling(iptv_service):
    # Test error handling when playlist fetch fails
    with patch.object(iptv_service.client, 'get', side_effect=Exception("Network Error")):
        channels = await iptv_service.fetch_playlist("http://bad-url.com")
        assert channels == []
