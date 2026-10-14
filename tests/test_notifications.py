"""System notifications: the pieces that had no feedback before.

The in-app toast lives in the Flet control tree, and the Android fullscreen
route is pushed above that tree, so a screenshot or favourite toggle taken in
fullscreen produced nothing at all. These pin the notification calls, the
channel split (silent for actions, audible for alerts), and the
dead-to-live transition that decides when a "back online" alert is earned.
"""

import asyncio

import pytest

from services import liveliness_checker as lc
from services.notify_service import (
    _CHANNEL_ALERT,
    _CHANNEL_FEEDBACK,
    notify_service,
)


class FakeService:
    """Records posts instead of reaching the OS."""

    def __init__(self):
        self.posted = []
        self.on_tap = None

    async def show(self, id, title=None, body=None, payload="", channel_id=None, **kw):
        self.posted.append(
            {
                "id": id,
                "title": title,
                "body": body,
                "payload": payload,
                "channel": channel_id,
            }
        )

    async def are_notifications_enabled(self):
        return True

    async def create_notification_channel(self, channel):
        self.posted.append({"channel_created": channel.id})


@pytest.fixture
def fake_backend(monkeypatch):
    fake = FakeService()
    monkeypatch.setattr(notify_service, "_service", fake, raising=False)
    monkeypatch.setattr(notify_service, "_started", True, raising=False)
    monkeypatch.setattr(notify_service, "_ready", True, raising=False)
    monkeypatch.setattr(notify_service, "_channels_made", True, raising=False)
    monkeypatch.setattr(notify_service, "_tap_handler", None, raising=False)
    return fake


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    monkeypatch.setattr(lc, "_was_dead", set(), raising=False)
    monkeypatch.setattr(lc, "notify_service", notify_service, raising=False)


@pytest.mark.anyio
async def test_feedback_posts_on_the_silent_channel(fake_backend):
    assert await notify_service.feedback("Screenshot saved", "a.mkv") is True
    post = fake_backend.posted[-1]
    assert post["title"] == "Screenshot saved"
    assert post["channel"] == _CHANNEL_FEEDBACK


@pytest.mark.anyio
async def test_recovery_posts_on_the_alert_channel_with_a_deep_link(fake_backend):
    """A tap must land in the player, so the payload is a ktv:// link."""
    await notify_service.alert(
        "X is back online", "Tap to watch", payload="ktv://play?url=AAA"
    )
    post = fake_backend.posted[-1]
    assert post["channel"] == _CHANNEL_ALERT
    assert post["payload"].startswith("ktv://play?url=")


@pytest.mark.anyio
async def test_live_on_first_sighting_is_not_announced():
    """Starting on a healthy channel must not alert."""
    posted = []

    class Spy:
        async def alert(self, title, body="", payload=""):
            posted.append(title)

    lc.notify_service = Spy()
    await lc._maybe_announce_recovery("https://x/a.m3u8", True)
    assert posted == []


@pytest.mark.anyio
async def test_dead_then_live_announces_once():
    posted = []

    class Spy:
        async def alert(self, title, body="", payload=""):
            posted.append((title, payload))

    lc.notify_service = Spy()
    url = "https://x/a.m3u8"
    await lc._maybe_announce_recovery(url, False)
    assert url in lc._was_dead
    await lc._maybe_announce_recovery(url, True)
    await lc._maybe_announce_recovery(url, True)
    assert len(posted) == 1
    assert posted[0][0].endswith("is back online")


def test_missing_dependency_degrades_to_no_op(monkeypatch):
    """Without flet_notifications installed nothing may raise."""
    import services.notify_service as mod

    monkeypatch.setattr(mod, "_HAS_NOTIFICATIONS", False)
    assert asyncio.run(notify_service.feedback("t", "b")) is False
    assert asyncio.run(notify_service.ensure_ready()) is False


def test_tap_handler_is_applied_to_the_service(fake_backend, monkeypatch):
    seen = []
    monkeypatch.setattr(notify_service, "_service", fake_backend, raising=False)
    notify_service.set_tap_handler(lambda e: seen.append(e))
    assert fake_backend.on_tap is not None
    fake_backend.on_tap("event")
    assert seen == ["event"]
