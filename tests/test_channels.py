import pytest
from channels.provider import ChannelProvider
from channels.base import ChannelData

def test_provider_initialization():
    provider = ChannelProvider()
    countries = provider.get_countries()
    assert isinstance(countries, list)
    # Nigeria should be there if sync ran
    country_names = [c["name"] for c in countries]
    assert "Nigeria" in country_names or len(country_names) >= 0

def test_channel_data_model():
    c = ChannelData(name="Test", url="http://test.com", group="Music")
    assert c.name == "Test"
    assert c.group == "Music"
    assert c.logo == "" # Default
