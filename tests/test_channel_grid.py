"""Tests for ChannelGrid component."""

import flet as ft

from app_next.components.channel_grid import ChannelGrid


def _make_ch(idx):
    return {"url": f"http://x/{idx}", "name": f"Channel {idx}", "logo": ""}


def test_channel_grid_is_a_grid_view():
    grid = ChannelGrid(
        channels=[_make_ch(0)],
        favorites_set=set(),
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_cache_obj=None,
        ad_service=None,
    )
    assert isinstance(grid, ft.GridView)


def test_channel_grid_renders_one_card_per_channel():
    channels = [_make_ch(i) for i in range(5)]
    grid = ChannelGrid(
        channels=channels,
        favorites_set=set(),
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_cache_obj=None,
        ad_service=None,
    )
    # The GridView's controls include Card-wrapping containers with `col` attribute
    card_wrappers = [
        c for c in grid.controls if isinstance(c, ft.Container) and hasattr(c, "col")
    ]
    assert len(card_wrappers) == 5


def test_channel_grid_keyed_with_url():
    channels = [_make_ch(0), _make_ch(1)]
    grid = ChannelGrid(
        channels=channels,
        favorites_set=set(),
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_cache_obj=None,
        ad_service=None,
    )
    # Cards in GridView are wrapped in Containers — check their content
    for c in grid.controls:
        if isinstance(c, ft.Container) and hasattr(c, "content"):
            inner = c.content
            if isinstance(inner, ft.Container) and inner.key is not None:
                assert "http://x/0" in str(inner.key) or "http://x/1" in str(inner.key)
                return
    assert False, "No keyed ChannelCard found in GridView"


def test_channel_grid_empty_with_no_channels():
    grid = ChannelGrid(
        channels=[],
        favorites_set=set(),
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_cache_obj=None,
        ad_service=None,
    )
    # Empty channels returns EmptyState, which is a Container
    assert isinstance(grid, ft.Container)
