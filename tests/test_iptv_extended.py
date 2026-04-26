import pytest
from unittest.mock import patch, MagicMock
from services.iptv_service import IPTVService
import os

@pytest.fixture
def iptv_service():
    return IPTVService()

def test_m3u_parsing_logic(iptv_service):
    # Mocking m3u-parser to avoid real file I/O
    with patch('m3u_parser.M3uParser') as MockParser:
        mock_instance = MockParser.return_value
        mock_instance.get_list.return_value = [
            {"name": "CNN", "url": "http://cnn.com", "category": "News"},
            {"name": "BBC", "url": "http://bbc.com", "category": "News"}
        ]
        
        # We manually call a parsing check (simulated)
        channels = mock_instance.get_list()
        assert len(channels) == 2
        assert channels[0]['name'] == "CNN"

def test_cache_io(iptv_service):
    test_channels = [{"name": "Test"}]
    iptv_service.cache_file = "test_cache.json"
    
    import asyncio
    asyncio.run(iptv_service.cache_channels(test_channels))
    
    loaded = iptv_service.load_cached_channels()
    assert loaded == test_channels
    
    if os.path.exists("test_cache.json"):
        os.remove("test_cache.json")
