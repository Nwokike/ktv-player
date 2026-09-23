"""D-pad focus pop (TV-UX wave 1) — the scale lift on focused cards."""

from types import SimpleNamespace

from components.channel_card import ChannelCard
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
    card = VideoCard(video=LocalVideo(name="v.mp4", path="/v.mp4", size=1), on_play=lambda p: None)
    card.on_focus(SimpleNamespace())
    assert card.scale == 1.04
    card.on_blur(SimpleNamespace())
    assert card.scale == 1.0


def test_focus_handlers_survive_unattached_cards():
    # Cards are built before they are mounted in unit tests — update()
    # raises there, and the handlers must swallow it.
    card = _channel_card()
    card.on_focus(SimpleNamespace())
    card.on_blur(SimpleNamespace())
