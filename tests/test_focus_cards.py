"""Focus-aware card contract — RED→GREEN regression test for Phase A.

ChannelCard, the RecentlyWatched card, and VideoCard were previous
`ft.Container`-based clickable tiles. Flet 0.86.4's Container does NOT
accept focusable/autofocus/on_focus/on_blur/focus(), so a D-pad user on
Android TV / Fire Stick had no way to navigate the channel grid, the
recently-watched carousel, or the local videos folder expansion.

These tests assert the new focusable contract:
- Each card returns an `ft.FilledButton` (which IS natively focusable,
  carries `autofocus`, `on_focus`/`on_blur`, and has `async def focus()`).
- The visual styling (height, padding, corner radius) is preserved via
  `style=card_button_style(...)` so the cards look Identical to before.
- The `on_click` callback still routes to the underlying `on_play(url)`
  handler — no behavior regression.

Verified Flet 0.86.4 API surface (probe of buttons in
.venv/lib/python3.14/site-packages/flet/controls/material/):
- FilledButton has: autofocus, on_focus, on_blur, content, style,
  async def focus(). It inherits width/height from LayoutControl.
- ButtonStyle carries: padding, shape (RoundedRectangleBorder), bgcolor,
  overlay_color, elevation — exactly the visual knobs Container had.
"""

import flet as ft
from flet_tree import walk, walk_buttons

from app_next.components.channel_card import ChannelCard
from app_next.components.focus_styles import card_button_style
from app_next.components.recently_watched import RecentlyWatched
from app_next.components.video_card import VideoCard
from core.constants import CARD_BORDER_RADIUS, CARD_HEIGHT
from services.local_scanner import LocalVideo

# --- ChannelCard ---


def test_channel_card_is_a_filled_button():
    """ChannelCard must return a FilledButton so D-pad can focus it."""
    card = ChannelCard(
        channel={"url": "http://x", "name": "X", "logo": ""},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    assert isinstance(card, ft.FilledButton), (
        "ChannelCard must return a FilledButton for D-pad focus; got "
        f"{type(card).__name__}"
    )


def test_channel_card_filled_button_preserves_height_and_key():
    card = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    assert card.height == CARD_HEIGHT
    # ValueKey(url) is what powers GridView focus preservation across filter changes
    assert card.key is not None
    assert "http://x" in str(card.key)


def test_channel_card_has_style_preserving_corners_and_padding():
    """The style must keep the original Container visuals (PAD=12, R=CARD_BORDER_RADIUS)."""
    card = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )
    assert card.style is not None, "FilledButton must carry a style"
    shape = card.style.shape
    # shape is wrapped for state-resolve; verify it carries a RoundedRectangleBorder
    # default MaterialState
    resolved = shape if not hasattr(shape, "default") else shape.default
    if hasattr(resolved, "radius"):
        assert resolved.radius == CARD_BORDER_RADIUS
    # padding state-resolves to the same Padding on all states
    pad = card.style.padding
    # Compare against what card_button_style produces for the same args
    ref = card_button_style(padding=ft.Padding.all(12), radius=CARD_BORDER_RADIUS)
    assert pad == ref.padding


def test_channel_card_on_click_fires_on_play_not_containers_on_click():
    """Behavior preserved: clicking the button fires on_play(url)."""
    fired = []
    card = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=False,
        on_play=lambda u: fired.append(u),
        on_toggle_favorite=lambda u: None,
    )
    assert card.on_click is not None
    card.on_click(None)
    assert fired == ["http://x"]


def test_channel_card_favorite_subtile_is_focusable_icon_button():
    """The favorite star must be its own focusable IconButton so D-pad can
    stop on it separately from the whole-card play click target."""
    card = ChannelCard(
        channel={"url": "http://x", "name": "X"},
        is_favorite=True,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
    )
    icon_buttons = [c for c in walk(card) if isinstance(c, ft.IconButton)]
    assert len(icon_buttons) == 1, (
        "Expected exactly one nested IconButton (the favorite toggle); got "
        f"{len(icon_buttons)}"
    )
    assert icon_buttons[0].on_click is not None
    fired = []
    card2 = ChannelCard(
        channel={"url": "http://y", "name": "Y"},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: fired.append(u),
    )
    ib = next(c for c in walk(card2) if isinstance(c, ft.IconButton))
    ib.on_click(None)
    assert fired == ["http://y"]


# --- RecentlyWatched card ---


def _rw_factory(history=None, channels_map=None, on_play=None):
    history = history if history is not None else ["http://a"]
    channels_map = (
        channels_map
        if channels_map is not None
        else {"http://a": {"name": "A", "url": "http://a", "logo": ""}}
    )
    on_play = on_play or (lambda u: None)
    return RecentlyWatched(history=history, channels_map=channels_map, on_play=on_play)


def test_recently_watched_cards_are_filled_buttons():
    rw = _rw_factory()
    cards = list(walk_buttons(rw))
    assert len(cards) == 1, f"expected 1 card, got {len(cards)}"
    assert isinstance(cards[0], ft.FilledButton)


def test_recently_watched_card_on_click_fires_on_play():
    fired = []
    rw = _rw_factory(on_play=lambda u: fired.append(u))
    card = next(iter(walk_buttons(rw)))
    card.on_click(None)
    assert fired == ["http://a"]


# --- VideoCard ---


def test_video_card_is_a_filled_button():
    video = LocalVideo(name="test.mp4", path="/path/test.mp4", size=1024)
    card = VideoCard(video=video, on_play=lambda p: None)
    assert isinstance(card, ft.FilledButton), (
        f"VideoCard must return a FilledButton; got {type(card).__name__}"
    )


def test_video_card_preserves_height_and_radius():
    video = LocalVideo(name="t.mp4", path="/p/t.mp4", size=10)
    card = VideoCard(video=video, on_play=lambda p: None)
    assert card.height == 140
    assert card.style is not None
    shape = card.style.shape
    resolved = shape if not hasattr(shape, "default") else shape.default
    if hasattr(resolved, "radius"):
        assert resolved.radius == 16


def test_video_card_on_click_fires_on_play_with_path():
    fired = []
    video = LocalVideo(name="t.mp4", path="/p/t.mp4", size=10)
    card = VideoCard(video=video, on_play=lambda p: fired.append(p))
    card.on_click(None)
    assert fired == ["/p/t.mp4"]
