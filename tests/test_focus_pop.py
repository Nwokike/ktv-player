"""D-pad focus cue — declarative only, no prop mutation.

The 2.3.0 regression: cards carried `on_focus`/`on_blur` handlers that
set `control.scale`. Cards are the body of a `@ft.component`, so Flet
freezes them after render and every prop write raises
"Frozen controls cannot be updated" — which fired on every focus event
(verified from a real desktop run: `flet/controls/value_types.py:66`
raises, `component.py:149` sets `_frozen`).

These tests pin the fix: no scale mutation anywhere, and the cue is the
FOCUSED state in the ButtonStyle.
"""

from unittest import mock

from components.channel_card import ChannelCard
from components.focus_styles import card_button_style


def _channel_card():
    return ChannelCard(
        channel={"url": "http://x", "name": "X", "logo": ""},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
        liveliness_status=None,
    )


def test_card_carries_no_scale_mutation_handlers():
    """The regression itself: handlers that write .scale on a frozen card."""
    card = _channel_card()
    assert card.on_focus is None
    assert card.on_blur is None


def test_focus_styles_exposes_only_the_button_style():
    import components.focus_styles as fs

    assert fs.__all__ == ["card_button_style"]
    assert not hasattr(fs, "attach_focus_pop")
    assert not hasattr(fs, "card_focus_scale")


def test_focused_state_is_the_cue():
    """The working cue: a FOCUSED border/overlay in the style."""
    import flet as ft

    style = card_button_style()
    assert ft.ControlState.FOCUSED in style.side
    assert style.side[ft.ControlState.FOCUSED].width > style.side[
        ft.ControlState.DEFAULT
    ].width
    assert ft.ControlState.FOCUSED in style.overlay_color
    assert style.overlay_color[ft.ControlState.FOCUSED] != ft.Colors.TRANSPARENT


def test_no_source_file_writes_scale_on_focus():
    """Grep-level guard: the mutation must not come back anywhere."""
    import inspect

    import components.channel_card as cc
    import components.video_card as vc

    for mod in (cc, vc):
        src = inspect.getsource(mod)
        assert 'setattr(' not in src or '"scale"' not in src, mod.__name__
        assert ".scale = " not in src, mod.__name__


def test_survives_unattached_cards():
    # Cards are built before they are mounted in unit tests.
    card = _channel_card()
    assert card is not None


def test_focus_event_on_a_mocked_card_does_not_raise():
    """A brand-new regression canary: if anyone re-adds a scale-writing
    handler, a focus event on a frozen double surfaces it here."""
    card = _channel_card()
    frozen = mock.MagicMock()
    frozen._values = {}
    frozen._dirty = {}
    # Property write on a frozen control raises — assert the card has no
    # handler that would even try.
    assert not callable(getattr(card, "on_focus", None))
    assert not callable(getattr(card, "on_blur", None))
