"""Tests for ChannelGrid component."""

from components.channel_grid import ChannelGrid


def test_channel_grid_is_component():
    assert getattr(ChannelGrid, "__is_component__", False) is True
    assert callable(ChannelGrid)
