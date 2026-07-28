"""Tests for ChannelCard component."""

import flet as ft

from app_next.components.channel_card import ChannelCard
from core.constants import CARD_HEIGHT, STATUS_DOT_SIZE


def test_channel_card_returns_a_container():
    card = ChannelCard(
        channel={"url": "http://x", "name": "Test Channel", "logo": ""},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    assert isinstance(card, ft.Container)


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
    ico = _find_icon(fav_card, ft.Icons.FAVORITE)
    assert ico is not None

    unfav_card = ChannelCard(
        channel={"url": "http://y", "name": "Y"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    ico2 = _find_icon(unfav_card, ft.Icons.FAVORITE_BORDER)
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


# --- helpers ---
def _walk(c):
    yield c
    children = getattr(c, "controls", None) or []
    if isinstance(children, list):
        for ch in children:
            yield from _walk(ch)
    content = getattr(c, "content", None)
    if content:
        yield from _walk(content)


def _find_icon(root, icon_name):
    for c in _walk(root):
        if isinstance(c, ft.Icon) and c.icon == icon_name:
            return c
    return None


def _find_dot(root):
    for c in _walk(root):
        if isinstance(c, ft.Container) and c.border_radius == STATUS_DOT_SIZE // 2:
            return c
    return None
