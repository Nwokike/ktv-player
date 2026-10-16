"""System notifications: the pieces that had no feedback before.

The in-app toast lives in the Flet control tree, and the Android fullscreen
route is pushed above that tree, so a screenshot or favourite toggle taken in
fullscreen produced nothing at all. These pin the notification calls, the
channel split (silent for actions, audible for alerts), and the
dead-to-live transition that decides when a "back online" alert is earned.
"""

import asyncio
from types import SimpleNamespace

import pytest

from services import liveliness_checker as lc
from services.notify_service import (
    _CHANNEL_ALERT,
    _CHANNEL_FEEDBACK,
    notify_service,
)


class FakeService:
    """Records posts instead of reaching the OS.

    ``drain_posts`` runs the fire-and-forget tasks a caller scheduled through
    the fake page: the real ``page.run_task`` takes a coroutine *function* and
    schedules the result, so a post only becomes visible once the loop runs it.
    ``page.run_task`` is stubbed by ``schedule`` so callers can be exercised
    without a page at all.
    """

    def __init__(self):
        self.posted = []
        self.on_tap = None
        self._scheduled: list = []

    def schedule(self, fn, *args, **kwargs):
        coro = fn(*args, **kwargs)
        self._scheduled.append(coro)
        return coro

    async def drain_posts(self):
        pending, self._scheduled = self._scheduled, []
        for coro in pending:
            if hasattr(coro, "__await__"):
                await coro

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


# --- premium entitlement notifications ---


@pytest.fixture
def premium_with_backend(monkeypatch, fake_backend):
    """A PremiumService whose licence verdict and page I control."""
    from services.premium_service import PremiumService

    svc = PremiumService.__new__(PremiumService)
    # run_task -> the fake's schedule, so drains actually run the posts.
    svc.page = SimpleNamespace(run_task=fake_backend.schedule)
    svc._premium_announced = False
    svc._listeners = []
    svc._notify_listeners = lambda: None

    class _Lic:
        def __init__(self):
            self.unlocked = True

    svc.license = _Lic()
    svc._recompute_premium = PremiumService._recompute_premium.__get__(svc)
    return svc


@pytest.mark.anyio
async def test_revoke_announces_once(fake_backend, premium_with_backend):
    """A revoke or expiry is silent today. One alert, not one per tick."""
    from core.state import state

    state.is_premium = True
    premium_with_backend._recompute_premium()
    assert fake_backend.posted == []

    premium_with_backend.license.unlocked = False
    for _ in range(3):
        premium_with_backend._recompute_premium()
    await fake_backend.drain_posts()

    posts = [p for p in fake_backend.posted if p["title"] == "Premium ended"]
    assert len(posts) == 1
    assert posts[0]["channel"] == _CHANNEL_ALERT


@pytest.mark.anyio
async def test_relock_then_revoke_announces_again(fake_backend, premium_with_backend):
    """The latch is per-downgrade, not permanent."""
    from core.state import state

    state.is_premium = True
    premium_with_backend.license.unlocked = False
    premium_with_backend._recompute_premium()
    await fake_backend.drain_posts()
    assert premium_with_backend._premium_announced is True

    premium_with_backend.license.unlocked = True
    premium_with_backend._recompute_premium()
    assert premium_with_backend._premium_announced is False

    premium_with_backend.license.unlocked = False
    premium_with_backend._recompute_premium()
    await fake_backend.drain_posts()
    ended = [p for p in fake_backend.posted if p["title"] == "Premium ended"]
    assert len(ended) == 2


@pytest.mark.anyio
async def test_unlock_does_not_announce_from_recompute(
    fake_backend, premium_with_backend
):
    """An unlock has its own better-worded notification at the watcher, so
    the shared funnel must not double up on it."""
    from core.state import state

    state.is_premium = False
    premium_with_backend.license.unlocked = True
    premium_with_backend._recompute_premium()
    await fake_backend.drain_posts()
    assert fake_backend.posted == []
