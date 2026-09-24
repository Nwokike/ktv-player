"""Tests for IMA (Google video ads) integration — Android TV pre-roll.

IMA replaces the AdMob interstitial on TV only; phones keep the current
AdMob behavior. Premium users see no ads at all.
"""

import asyncio
from types import SimpleNamespace
from unittest import mock

import flet as ft
import pytest

from core.state import state
from services.ad_service import AdService


@pytest.fixture(autouse=True)
def _clean_state():
    state.reset()
    yield
    state.reset()


@pytest.fixture(autouse=True)
def _patch_db():
    dbm = mock.MagicMock()
    dbm.get_history_entry_sync.return_value = None
    dbm.update_history_position = mock.AsyncMock()
    with mock.patch("components.player.immersive_player.db_manager", dbm):
        yield dbm


@pytest.fixture
def page(fake_page):
    fake_page.platform = SimpleNamespace(is_mobile=lambda: True)
    return fake_page


def _ima():
    ima = mock.MagicMock()
    for name in (
        "request_ads",
        "set_content_progress",
        "content_complete",
        "destroy",
        "start",
        "pause",
        "resume",
    ):
        setattr(ima, name, mock.AsyncMock())
    return ima


def _player(page, tv=False, ad_service=None, ima_tag="tag", **kw):
    from components.player import immersive_player as ip

    # `tv` no longer gates IMA (mobile-wide) — kept for test readability.
    with mock.patch.object(
        ip.ImmersivePlayer,
        "safe_page",
        new_callable=mock.PropertyMock,
        return_value=page,
    ):
        p = ip.ImmersivePlayer(
            resource="http://example.com/vod.mp4",
            source_url="http://example.com/vod.mp4",
            title="T",
            ad_service=ad_service,
            ima_tag=ima_tag,
            **kw,
        )
    p._mock_page = page
    p.update = mock.Mock()
    p.video.play = mock.AsyncMock()
    p.video.pause = mock.AsyncMock()
    p.video.stop = mock.AsyncMock()
    p.video.is_playing = mock.AsyncMock(return_value=True)
    p.video.update = mock.Mock()
    p.video.get_current_position = mock.AsyncMock(return_value=ft.Duration(seconds=30))
    p.video.get_duration = mock.AsyncMock(return_value=ft.Duration(seconds=600))
    p._start_watchdog = mock.Mock()
    p._arm_auto_pip = mock.Mock()
    p._disarm_auto_pip = mock.Mock()
    p._disable_auto_pip = mock.Mock()
    return p


def _run_task_fns(page):
    return [fn for fn, _args, _kwargs in page._run_task_calls]


# --- View construction ---


def test_phone_has_ima_view(page):
    """IMA is on every mobile build — the phone is the test rig with logs."""
    p = _player(page, tv=False)
    assert p.ima_view is not None
    assert len(p.controls) == 4  # black, video, ima, overlay


def test_tv_has_ima_view_in_stack(page):
    p = _player(page, tv=True)
    assert p.ima_view is not None
    assert len(p.controls) == 4  # + bounded IMA container, overlay still last
    assert p.controls[-1] is p.overlay
    assert p.controls[2].content is p.ima_view


def test_no_tag_disables_ima(page):
    p = _player(page, tv=True, ima_tag="")
    assert p.ima_view is None


# --- start_playback: who owns the pre-roll ---


@pytest.mark.asyncio
async def test_phone_start_skips_interstitial_and_arms_ima(page):
    """AdMob interstitial is off (master switch); IMA owns the pre-roll."""
    ads = mock.AsyncMock()
    p = _player(page, tv=False, ad_service=ads)

    await p.start_playback()

    ads.show_interstitial.assert_not_awaited()
    assert p._ima_request_soon in _run_task_fns(page)


@pytest.mark.asyncio
async def test_tv_start_skips_interstitial_and_arms_ima(page):
    ads = mock.AsyncMock()
    p = _player(page, tv=True, ad_service=ads)

    await p.start_playback()

    ads.show_interstitial.assert_not_awaited()
    p.video.play.assert_awaited_once()
    assert p._ima_request_soon in _run_task_fns(page)


@pytest.mark.asyncio
async def test_tv_start_premium_arms_nothing(page):
    state.is_premium = True
    ads = mock.AsyncMock()
    p = _player(page, tv=True, ad_service=ads)

    await p.start_playback()

    ads.show_interstitial.assert_not_awaited()
    assert p._ima_request_soon not in _run_task_fns(page)


# --- Request lifecycle ---


@pytest.mark.asyncio
async def test_ima_request_sends_duration_and_is_latched(page):
    p = _player(page, tv=True)
    ima = _ima()
    p.ima_view = ima
    p._last_duration = 600.0

    await p._ima_maybe_request()
    await p._ima_maybe_request()  # latched — no second request

    ima.request_ads.assert_awaited_once()
    assert ima.content_duration_ms == 600_000
    ima.update.assert_called_once()


@pytest.mark.asyncio
async def test_ima_request_premium_never_sends(page):
    state.is_premium = True
    p = _player(page, tv=True)
    ima = _ima()
    p.ima_view = ima
    p._last_duration = 600.0

    await p._ima_maybe_request(force=True)

    ima.request_ads.assert_not_awaited()


# --- Ad events drive the content player ---


@pytest.mark.asyncio
async def test_loaded_event_starts_ads(page):
    p = _player(page, tv=True)
    ima = _ima()
    p.ima_view = ima

    await p._on_ima_ad_event(SimpleNamespace(type="loaded"))

    ima.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_pause_and_resume_events_control_content(page):
    p = _player(page, tv=True)
    p.ima_view = _ima()

    await p._on_ima_ad_event(SimpleNamespace(type="contentPauseRequested"))
    assert p._ima_ad_active is True
    p.video.pause.assert_awaited_once()

    await p._on_ima_ad_event(SimpleNamespace(type="contentResumeRequested"))
    assert p._ima_ad_active is False
    p.video.play.assert_awaited()


# --- Content progress feed (throttled) ---


def test_progress_feed_throttled_to_200ms(page):
    p = _player(page, tv=True)
    ima = _ima()
    p.ima_view = ima
    p._last_duration = 600.0
    p._last_ima_push = 1e12  # far in the future — first tick suppressed

    p._on_pos_change(SimpleNamespace(data=30_000))
    assert ima.set_content_progress not in _run_task_fns(page)

    p._last_ima_push = 0.0
    p._on_pos_change(SimpleNamespace(data=30_000))
    p._on_pos_change(SimpleNamespace(data=31_000))  # throttled
    pushes = [c for c in page._run_task_calls if c[0] is ima.set_content_progress]
    assert len(pushes) == 1
    assert pushes[0][1] == (30_000, 600_000)


def test_progress_feed_suspended_during_ads(page):
    p = _player(page, tv=True)
    ima = _ima()
    p.ima_view = ima
    p._last_duration = 600.0
    p._last_ima_push = 0.0
    p._ima_ad_active = True

    p._on_pos_change(SimpleNamespace(data=30_000))

    assert ima.set_content_progress not in _run_task_fns(page)


# --- History checkpoints must ignore ad time ---


@pytest.mark.asyncio
async def test_checkpoint_suppressed_during_ad(page, _patch_db):
    p = _player(page, tv=True)
    p.ima_view = _ima()
    p._last_position = 30.0
    p._last_duration = 600.0
    p._last_position_save = 0.0
    p._ima_ad_active = True

    p._maybe_save_position_periodically()
    _patch_db.update_history_position.assert_not_called()

    p._ima_ad_active = False
    p._last_position_save = 0.0  # the suppressed call consumed the throttle
    p._maybe_save_position_periodically()
    # The checkpoint is scheduled via loop.create_task — let it start.
    await asyncio.sleep(0.01)
    _patch_db.update_history_position.assert_awaited()


# --- Completion + teardown ---


def test_vod_completion_sends_content_complete(page):
    p = _player(page, tv=True)
    ima = _ima()
    p.ima_view = ima
    p._last_position = 598.0
    p._last_duration = 600.0

    with mock.patch("components.player.handlers.handle_stream_complete"):
        p._on_complete(SimpleNamespace())

    assert ima.content_complete in _run_task_fns(page)


def test_live_end_does_not_send_content_complete(page):
    # Live stream: duration unknown / position not near the end.
    p = _player(page, tv=True)
    ima = _ima()
    p.ima_view = ima
    p._last_position = 5.0
    p._last_duration = 0.0

    with mock.patch("components.player.handlers.handle_stream_complete"):
        p._on_complete(SimpleNamespace())

    assert ima.content_complete not in _run_task_fns(page)


@pytest.mark.asyncio
async def test_close_destroys_ima(page):
    p = _player(page, tv=True)
    ima = _ima()
    p.ima_view = ima

    await p.handle_close()

    ima.destroy.assert_awaited_once()
    p.video.stop.assert_awaited()


@pytest.mark.asyncio
async def test_close_without_ima_is_noop(page):
    p = _player(page, tv=False)
    await p.handle_close()  # must not raise
    p.video.stop.assert_awaited()


# --- AdService: AdMob fully off on TV ---


@pytest.mark.asyncio
async def test_ad_service_suppressed_on_tv(page):
    svc = AdService(page)
    with mock.patch("services.ad_service.is_tv_device", return_value=True):
        assert svc.get_standard_banner_ad() is None
        assert svc.get_anchor_banner_ad() is None
        assert svc.get_native_style_ad() is None
        await svc.preload_interstitial()
        assert svc.interstitial is None
        assert svc._ad_loaded_event.is_set()
        assert await svc.show_interstitial() is False


@pytest.mark.asyncio
async def test_ad_service_phone_unchanged_with_switch_on(page):
    """With the master switch restored, phone AdMob behaves as before."""
    svc = AdService(page)
    with (
        mock.patch("services.ad_service.is_tv_device", return_value=False),
        mock.patch("services.ad_service.ADS_MOB_ENABLED", True),
    ):
        assert svc.get_standard_banner_ad() is not None
        await svc.preload_interstitial()
        assert svc.interstitial is not None


@pytest.mark.asyncio
async def test_ad_service_silent_with_switch_off(page):
    """Current default: AdMob fully off, no exceptions, no ads."""
    svc = AdService(page)
    with mock.patch("services.ad_service.ADS_MOB_ENABLED", False):
        assert svc.get_standard_banner_ad() is None
        await svc.preload_interstitial()
        assert svc.interstitial is None
        assert await svc.show_interstitial() is False
