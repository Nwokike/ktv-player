import pytest
import os
import shutil
from channels.provider import ChannelProvider
from channels.base import ChannelData

@pytest.fixture
def temp_data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    # Create a dummy module
    with open(d / "test_country.py", "w") as f:
        f.write('from channels.base import ChannelData\n')
        f.write('group_name = "Test Country"\n')
        f.write('country_code = "TC"\n')
        f.write('channels = [ChannelData(name="Test Channel", url="url", group="Test")]\n')
    return str(d)

def test_provider_initialization():
    provider = ChannelProvider()
    assert provider.data_dir is not None
    assert isinstance(provider.modules, dict)

def test_get_countries(temp_data_dir):
    provider = ChannelProvider(temp_data_dir)
    countries = provider.get_countries()
    assert len(countries) == 1
    assert countries[0]["name"] == "Test Country"
    assert countries[0]["code"] == "TC"

def test_get_all_channels(temp_data_dir):
    provider = ChannelProvider(temp_data_dir)
    channels = provider.get_all_channels()
    assert len(channels) == 1
    assert channels[0].name == "Test Channel"

def test_get_channels_by_country(temp_data_dir):
    provider = ChannelProvider(temp_data_dir)
    by_country = provider.get_channels_by_country()
    assert "Test Country" in by_country
    assert len(by_country["Test Country"]) == 1

def test_get_channels_by_category(temp_data_dir):
    provider = ChannelProvider(temp_data_dir)
    by_cat = provider.get_channels_by_category()
    assert "Test" in by_cat
    assert len(by_cat["Test"]) == 1

def test_channel_data_model():
    c = ChannelData(name="Test", url="http://test.com", group="Music")
    assert c.name == "Test"
    assert c.group == "Music"
    assert c.logo == ""
