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


# --- new-version notification ---


def _update(**kw):
    from types import SimpleNamespace

    base = {
        "version": "2.4.0",
        "build_number": 22,
        "type": "update",
        "mandatory": False,
        "github_url": "https://github.com/Nwokike/ktv-player/releases/latest",
    }
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def controller_for_updates(fake_backend):
    """An AppController with the fields _announce_update touches."""
    from main import AppController

    ctrl = object.__new__(AppController)
    ctrl.page = SimpleNamespace(run_task=fake_backend.schedule)
    ctrl._update_announced = None
    ctrl.notify_service = notify_service
    return ctrl


@pytest.mark.anyio
async def test_update_announces_once_per_version(fake_backend, controller_for_updates):
    """A boot-time check runs every launch; it must not re-announce."""
    controller_for_updates._announce_update(_update())
    await fake_backend.drain_posts()
    assert len(fake_backend.posted) == 1
    assert "2.4.0 is available" in fake_backend.posted[0]["title"]

    controller_for_updates._announce_update(_update())
    await fake_backend.drain_posts()
    assert len(fake_backend.posted) == 1, "same version re-announced"


@pytest.mark.anyio
async def test_new_version_announces_again(fake_backend, controller_for_updates):
    controller_for_updates._announce_update(_update())
    await fake_backend.drain_posts()
    controller_for_updates._update_announced = None
    controller_for_updates._announce_update(_update(version="2.5.0"))
    await fake_backend.drain_posts()
    titles = [p["title"] for p in fake_backend.posted]
    assert "KTV Player 2.4.0 is available" in titles
    assert "KTV Player 2.5.0 is available" in titles


@pytest.mark.anyio
async def test_mandatory_update_does_not_post(fake_backend, controller_for_updates):
    """A mandatory update already opens the version dialog in the
    foreground, so a shade entry adds nothing."""
    controller_for_updates._announce_update(_update(mandatory=True))
    await fake_backend.drain_posts()
    assert fake_backend.posted == []


@pytest.mark.anyio
async def test_update_payload_is_the_release_url(fake_backend, controller_for_updates):
    """The tap must open the browser, so the payload is a URL, and the tap
    handler has to route http(s) differently from ktv:// links."""
    controller_for_updates._announce_update(_update())
    await fake_backend.drain_posts()
    payload = fake_backend.posted[0]["payload"]
    assert payload.startswith("https://")

    # The deep-link parser gates to ktv:// only, so a URL must not reach it.
    from core.deeplink import parse_deep_link

    assert parse_deep_link(payload) == (None, None, None, None)


# --- local scan finished ---


class _FakeVideo:
    def __init__(self, path):
        self.path = path


class _FakeFolder:
    def __init__(self, *paths):
        self.videos = [_FakeVideo(p) for p in paths]


class _FakePage:
    """Records the (fn, args) pairs handed to run_task."""

    def __init__(self):
        self.calls = []

    def run_task(self, fn, *args, **kwargs):
        self.calls.append((fn, args))


@pytest.mark.parametrize(
    "previous,result,background,want",
    [
        # A real gain is announced.
        ([], [_FakeFolder("/a.mp4", "/b.mp4")], False, 1),
        ([], [_FakeFolder("/a.mp4")], False, 1),
        # An unchanged rescan is silent.
        ([_FakeFolder("/a.mp4")], [_FakeFolder("/a.mp4")], False, 0),
        # The post-delete background refresh only removed something.
        ([_FakeFolder("/a.mp4", "/b.mp4")], [_FakeFolder("/a.mp4")], True, 0),
        # Videos moving between folders is not a gain.
        (
            [_FakeFolder("/a.mp4", "/b.mp4")],
            [_FakeFolder("/a.mp4"), _FakeFolder("/b.mp4")],
            False,
            0,
        ),
        # Nothing found is silent.
        ([_FakeFolder("/a.mp4")], [], False, 0),
    ],
)
def test_scan_announces_only_a_real_gain(previous, result, background, want):
    from screens.local_screen import _announce_scan_result

    page = _FakePage()
    _announce_scan_result(page, previous, result, background=background)
    assert len(page.calls) == want


@pytest.mark.anyio
async def test_scan_uses_its_own_id(fake_backend):
    """It fills the reserved scan slot, not the generic feedback id, so a
    finished scan replaces any progress bar the same job was showing."""
    await notify_service.scan_finished("Videos found", "2 new videos")
    post = fake_backend.posted[-1]
    assert post["title"] == "Videos found"
    assert post["id"] == 4102


def test_scan_wording_is_pluralised():
    from screens.local_screen import _announce_scan_result

    one = _FakePage()
    _announce_scan_result(one, [], [_FakeFolder("/a.mp4")], background=False)
    assert one.calls[0][1][1] == "1 new video on this device"

    two = _FakePage()
    _announce_scan_result(two, [], [_FakeFolder("/a.mp4", "/b.mp4")], background=False)
    assert two.calls[0][1][1] == "2 new videos on this device"


# --- playlist refresh results ---


@pytest.fixture
def app_loader_state(monkeypatch):
    """A clean channel list plus a silenceable foreground flag."""
    from core import app_loader
    from core.state import state

    state.channels = [{"url": "/a"}, {"url": "/b"}]
    app_loader._foreground_refresh[0] = False
    yield app_loader
    app_loader._foreground_refresh[0] = False


def _refresh_page(fake_backend):
    return SimpleNamespace(run_task=fake_backend.schedule)


@pytest.mark.anyio
async def test_background_refresh_announces_the_delta(fake_backend, app_loader_state):
    """A premium tier flip refetches behind the user's back and the grid
    silently swaps — this is the case that had no feedback at all."""
    app_loader_state._announce_refresh(
        _refresh_page(fake_backend),
        [{"url": "/a"}, {"url": "/b"}, {"url": "/c"}, {"url": "/d"}],
    )
    await fake_backend.drain_posts()
    assert len(fake_backend.posted) == 1
    assert fake_backend.posted[0]["title"] == "Channels updated"
    assert "2 new channels" in fake_backend.posted[0]["body"]


@pytest.mark.anyio
async def test_foreground_refresh_is_exempt(fake_backend, app_loader_state):
    """The refresh button already toasts, so no shade entry as well."""
    app_loader_state.begin_foreground_refresh()
    app_loader_state._announce_refresh(
        _refresh_page(fake_backend),
        [{"url": "/a"}, {"url": "/c"}],
    )
    await fake_backend.drain_posts()
    assert fake_backend.posted == []


@pytest.mark.anyio
async def test_the_foreground_flag_resets(fake_backend, app_loader_state):
    """Exempting one refresh must not disable every later one."""
    app_loader_state.begin_foreground_refresh()
    app_loader_state._announce_refresh(_refresh_page(fake_backend), [{"url": "/z"}])
    await fake_backend.drain_posts()
    assert fake_backend.posted == []

    # A background refresh right after must still announce.
    app_loader_state._announce_refresh(_refresh_page(fake_backend), [{"url": "/z"}])
    await fake_backend.drain_posts()
    assert len(fake_backend.posted) == 1


@pytest.mark.anyio
async def test_unchanged_refresh_is_silent(fake_backend, app_loader_state):
    app_loader_state._announce_refresh(
        _refresh_page(fake_backend), [{"url": "/a"}, {"url": "/b"}]
    )
    await fake_backend.drain_posts()
    assert fake_backend.posted == []


@pytest.mark.anyio
async def test_channels_only_lost_is_reported(fake_backend, app_loader_state):
    """A playlist going dead removes channels; that is worth saying."""
    app_loader_state._announce_refresh(_refresh_page(fake_backend), [{"url": "/a"}])
    await fake_backend.drain_posts()
    assert "1 channel no longer available" in fake_backend.posted[0]["body"]


# --- foreground marks must never outlive their refresh ---


@pytest.mark.anyio
async def test_overlapping_foreground_refreshes_both_retire(
    fake_backend, app_loader_state
):
    """A count, not a flag: two foreground refreshes need two consumes, and
    a third (background) refresh after them must still announce."""
    page = SimpleNamespace(run_task=fake_backend.schedule)
    app_loader_state.begin_foreground_refresh()
    app_loader_state.begin_foreground_refresh()
    app_loader_state._announce_refresh(page, [{"url": "/a"}])
    app_loader_state._announce_refresh(page, [{"url": "/b"}])
    await fake_backend.drain_posts()
    assert fake_backend.posted == []

    app_loader_state._announce_refresh(page, [{"url": "/c"}])
    await fake_backend.drain_posts()
    assert len(fake_backend.posted) == 1


@pytest.mark.anyio
async def test_a_failed_load_does_not_strand_a_mark(fake_backend, app_loader_state):
    """An exception path must retire the mark too, or it would silently
    suppress the NEXT background refresh."""
    app_loader_state.begin_foreground_refresh()
    original = app_loader_state.channel_provider.get_all_channels

    async def _boom(*a, **k):
        raise RuntimeError("network down")

    app_loader_state.channel_provider.get_all_channels = _boom
    try:
        await app_loader_state.load_all_channels(
            SimpleNamespace(run_task=lambda *a: None), None
        )
    finally:
        app_loader_state.channel_provider.get_all_channels = original

    assert app_loader_state._foreground_refresh[0] == 0

    # A background refresh right after the failure still announces.
    app_loader_state._announce_refresh(
        SimpleNamespace(run_task=fake_backend.schedule), [{"url": "/zz"}]
    )
    await fake_backend.drain_posts()
    assert len(fake_backend.posted) == 1
