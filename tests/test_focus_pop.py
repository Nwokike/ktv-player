"""D-pad focus cue (TV-UX wave 1) — the scale lift on focused cards.

The cue is declarative: cards carry ``animate_scale`` plus on_focus /
on_blur handlers that set ``scale``. The FOCUSED border from
``card_button_style`` is the primary (always visible) cue; the scale
interpolates on top via the implicit animation.
"""

from types import SimpleNamespace

import pytest

from components.channel_card import ChannelCard
from components.focus_styles import card_button_style, card_focus_scale
from components.video_card import VideoCard
from services.local_scanner import LocalVideo


def _channel_card():
    return ChannelCard(
        channel={"url": "http://x", "name": "X", "logo": ""},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )


def test_channel_card_scales_up_on_focus_and_back_on_blur():
    card = _channel_card()
    card.on_focus(SimpleNamespace())
    assert card.scale == 1.04
    card.on_blur(SimpleNamespace())
    assert card.scale == 1.0


def test_video_card_scales_up_on_focus_and_back_on_blur():
    import flet as ft

    from tests.flet_tree import walk as _walk

    card = VideoCard(
        video=LocalVideo(name="v.mp4", path="/v.mp4", size=1), on_play=lambda p: None
    )
    surface = next(
        c
        for c in _walk(card)
        if isinstance(c, ft.FilledButton) and callable(getattr(c, "on_click", None))
    )
    surface.on_focus(SimpleNamespace())
    assert surface.scale == 1.04
    surface.on_blur(SimpleNamespace())
    assert surface.scale == 1.0


def test_focus_handlers_survive_unattached_cards():
    # Cards are built before they are mounted in unit tests — update()
    # raises there, and the handlers must swallow it.
    card = _channel_card()
    card.on_focus(SimpleNamespace())
    card.on_blur(SimpleNamespace())


def test_attach_focus_pop_is_gone():
    """The old mutating helper was deleted: grep-clean, no import."""
    import components.focus_styles as fs

    assert not hasattr(fs, "attach_focus_pop")
    assert "attach_focus_pop" not in fs.__all__


def test_cards_carry_animate_scale():
    """The cue must be visible: an implicit scale animation is declared."""
    import flet as ft

    from tests.flet_tree import walk as _walk

    card = _channel_card()
    assert card.animate_scale is not None
    video = VideoCard(
        video=LocalVideo(name="v.mp4", path="/v.mp4", size=1), on_play=lambda p: None
    )
    surface = next(
        c
        for c in _walk(video)
        if isinstance(c, ft.FilledButton) and callable(getattr(c, "on_click", None))
    )
    assert surface.animate_scale is not None


def test_card_button_style_has_pressed_and_disabled():
    """Press feedback must exist (transparent was a touch regression)."""
    import flet as ft

    style = card_button_style()
    assert ft.ControlState.PRESSED in style.side
    assert ft.ControlState.PRESSED in style.overlay_color
    assert ft.ControlState.DISABLED in style.side
    # Pressed overlay is fully visible, not a faint hover echo.
    assert style.overlay_color[ft.ControlState.PRESSED] != ft.Colors.TRANSPARENT


def test_card_button_style_validates_inputs():
    with pytest.raises(ValueError):
        card_button_style(overlay_alpha=2.0)
    with pytest.raises(ValueError):
        card_button_style(radius=-1)


def test_card_focus_scale_validates():
    with pytest.raises(ValueError):
        card_focus_scale(0)
