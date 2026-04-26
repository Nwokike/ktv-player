import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.iptv_service import IPTVService

@pytest.fixture
def iptv_service():
    return IPTVService()

@pytest.mark.asyncio
async def test_waterfall_logic(iptv_service):
    # Mock is_stream_working to fail for primary and succeed for fallback
    with patch.object(iptv_service, 'is_stream_working', side_effect=[False, True]):
        result = await iptv_service.get_stream_url_with_fallback(
            "ch1", 
            "http://primary.com", 
            ["http://fallback.com"]
        )
        assert result == "http://fallback.com"

@pytest.mark.asyncio
async def test_stream_health_check(iptv_service):
    # Mock the httpx client response
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    with patch.object(iptv_service.client, 'stream', return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response))):
        is_up = await iptv_service.is_stream_working("http://test.com")
        assert is_up is True
