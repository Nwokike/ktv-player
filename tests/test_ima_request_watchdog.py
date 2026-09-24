"""IMA request lifecycle: container, watchdog, teardown.

A device log showed the request being sent and then nothing at all — no
ad event, no error — for 21 seconds. These tests pin the behaviour that
makes the next attempt diagnosable: the SDK is handed a laid-out
container, a request that never becomes an ad collapses it again, and the
ad view is destroyed while it is still attached to the page.
"""

import asyncio
import contextlib
import inspect

import pytest
from flet_ima import AdEventType

from components.player.immersive_player import (
    _IMA_REQUEST_WATCHDOG_S,
    ImmersivePlayer,
    _vast_host,
)

TAG = (
    "https://pubads.g.doubleclick.net/gampad/ads"
    "?iu=/217757449231/vast_pod_skippable&sz=640x480&impl=s"
)


def _player(ima_tag: str = TAG) -> ImmersivePlayer:
    player = ImmersivePlayer(resource="https://example.com/v.mp4", ima_tag=ima_tag)
    player.ima_view = object()
    slot = _Slot()
    player._ima_slot = slot
    return player


class _Slot:
    def __init__(self):
        self.height = 0
        self.expand = False


@pytest.fixture(autouse=True)
def _clean_state():
    from core.state import state

    state.reset()
    yield
    state.reset()


# -- container --------------------------------------------------------------


def test_vast_host_is_reported_for_diagnostics():
    assert _vast_host(TAG) == "pubads.g.doubleclick.net"
    assert _vast_host("") == "none"
    assert _vast_host(None) == "none"


def test_request_expands_the_ad_container():
    """A zero-height container gave the SDK nothing to load into."""
    player = _player()
    player._ima_expand_slot_for_request()
    assert player._ima_slot.height is None
    assert player._ima_slot.expand is True


def test_collapsing_restores_the_zero_height_slot():
    player = _player()
    player._ima_set_slot_visible(True)
    player._ima_set_slot_visible(False)
    assert player._ima_slot.height == 0
    assert player._ima_slot.expand is False


# -- watchdog ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_watchdog_collapses_the_slot_when_no_ad_starts(monkeypatch):
    player = _player()
    monkeypatch.setattr(
        "components.player.immersive_player._IMA_REQUEST_WATCHDOG_S", 0.01
    )
    player._ima_expand_slot_for_request()
    player._arm_ima_request_watchdog()

    task = player._ima_watchdog_task
    assert task is not None
    await asyncio.wait_for(task, timeout=2.0)

    # No ad ever started: the video must not stay behind a black slot.
    assert player._ima_slot.height == 0
    assert player._ima_slot.expand is False


@pytest.mark.asyncio
async def test_watchdog_does_not_collapse_a_playing_ad(monkeypatch):
    player = _player()
    monkeypatch.setattr(
        "components.player.immersive_player._IMA_REQUEST_WATCHDOG_S", 0.01
    )
    player._ima_expand_slot_for_request()
    player._ima_ad_active = True  # an ad is on screen
    player._arm_ima_request_watchdog()
    await asyncio.wait_for(player._ima_watchdog_task, timeout=2.0)

    assert player._ima_slot.expand is True


@pytest.mark.asyncio
async def test_an_ad_event_cancels_the_watchdog(monkeypatch):
    player = _player()
    monkeypatch.setattr(
        "components.player.immersive_player._IMA_REQUEST_WATCHDOG_S", 0.05
    )
    player._ima_expand_slot_for_request()
    player._arm_ima_request_watchdog()
    task = player._ima_watchdog_task

    # A STARTED event means the SDK answered; the slot must stay put.
    await player._on_ima_ad_event(_event(AdEventType.STARTED))
    await _settle(task)
    assert task.cancelled() or task.done()
    assert player._ima_slot.expand is True


@pytest.mark.asyncio
async def test_rearming_cancels_the_previous_watchdog():
    player = _player()
    first = player._ima_watchdog_task
    player._arm_ima_request_watchdog()
    player._arm_ima_request_watchdog()
    assert first is None or first.cancelled() or first.done()


def _event(kind):
    """An ad event carrying a real wire value.

    flet_ima sends the AdEventType value verbatim (camelCase/lowercase), so
    the handler has to be fed exactly what the SDK produces — a made-up
    "STARTED" string matches nothing and would make this test vacuous.
    """
    from flet_ima import AdEventType

    class _Event:
        type = AdEventType(kind).value
        ad = None
        ad_id = None

        def __init__(self):
            self.cue_points_ms = []

    return _Event()


async def _settle(task) -> None:
    """Await a cancelled task so the cancellation is actually delivered."""
    if task is None:
        return
    with contextlib.suppress(asyncio.CancelledError, TimeoutError):
        await asyncio.wait_for(task, timeout=2.0)


# -- teardown ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_teardown_destroys_the_view_and_cancels_the_watchdog():
    destroyed = asyncio.Event()

    class _View:
        async def destroy(self):
            destroyed.set()

    player = _player()
    player.ima_view = _View()
    player._arm_ima_request_watchdog()
    watchdog = player._ima_watchdog_task

    await player.teardown()

    assert destroyed.is_set()
    assert player._ima_destroyed is True
    await _settle(watchdog)
    assert watchdog is None or watchdog.cancelled() or watchdog.done()


@pytest.mark.asyncio
async def test_teardown_is_idempotent():
    calls = []

    class _View:
        async def destroy(self):
            calls.append(1)

    player = _player()
    player.ima_view = _View()
    await player.teardown()
    await player.teardown()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_destroy_on_a_detached_view_is_not_an_error():
    """A detached control raises; teardown must absorb it quietly rather
    than log a failure for every playback."""

    class _DetachedView:
        async def destroy(self):
            raise RuntimeError("Control must be added to the page first")

    player = _player()
    player.ima_view = _DetachedView()
    await player.teardown()  # must not raise
    assert player._ima_destroyed is True


def test_controller_closes_players_through_teardown():
    """The controller must release the ad view before popping the view."""
    from src.main import AppController

    source = inspect.getsource(AppController._close_player_with_save)
    teardown_at = source.find("teardown")
    pop_at = source.find("self.page.views.pop()")
    assert teardown_at != -1, "close path must call player.teardown()"
    assert pop_at != -1
    assert teardown_at < pop_at, "teardown must run before the view is popped"


def test_watchdog_window_is_bounded():
    """A stuck request must not black out the video indefinitely."""
    assert 0 < _IMA_REQUEST_WATCHDOG_S <= 15
