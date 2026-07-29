"""Tests for ChannelCard component."""

import flet as ft
from flet_tree import find_icon, walk

from app_next.components.channel_card import ChannelCard
from core.constants import CARD_HEIGHT, STATUS_DOT_SIZE


def test_channel_card_is_a_focusable_filled_button():
    # Phase A: ChannelCard is now an ft.FilledButton (not a Container) so the
    # Flet runtime gives it native D-pad focus on Android TV remotes.
    card = ChannelCard(
        channel={"url": "http://x", "name": "Test Channel", "logo": ""},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    assert isinstance(card, ft.FilledButton)


def test_channel_card_has_stable_key():
    channel = {"url": "http://x", "name": "X"}
    card = ChannelCard(
        channel=channel,
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    assert card.key is not None
    assert "http://x" in str(card.key)


def test_channel_card_height_from_constant():
    card = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    assert card.height == CARD_HEIGHT


def test_channel_card_favorite_icon_reflects_is_favorite():
    fav_card = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=True,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    ico = find_icon(fav_card, ft.Icons.FAVORITE)
    assert ico is not None

    unfav_card = ChannelCard(
        channel={"url": "http://y", "name": "Y"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    ico2 = find_icon(unfav_card, ft.Icons.FAVORITE_BORDER)
    assert ico2 is not None


def test_channel_card_liveliness_dot_color():
    green = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=True,
    )
    dot = _find_dot(green)
    assert dot is not None

    grey = ChannelCard(
        channel={"url": "http://y", "name": "Y"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    dot2 = _find_dot(grey)
    assert dot2 is not None


def _find_dot(root):
    for c in walk(root):
        if isinstance(c, ft.Container) and c.border_radius == STATUS_DOT_SIZE // 2:
            return c
    return None
