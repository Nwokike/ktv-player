"""Regression tests for the deep-link cold-start hang and PiP-when-playing.

Root cause being locked in here (2026-08-30): v2.0.2 (549503a) made
play_stream share _loading_lock with the channel loader and silently DROP
the play request while a load was in flight. On a cold-start deep link the
loader always held the lock (remote playlist fetches, up to 20s each), so
the deep link was dropped and the user got a permanent blank screen — the
"open it two times" bug. Playback now has its own _play_lock.

PiP side: _build_params must explicitly call setAutoEnterEnabled(False)
when disarming (previously the setter was skipped, leaving auto-enter
armed on the Activity forever), and closing a deep-linked video must exit
to the calling app (Flet's window.close() is a desktop-only no-op on
Android, so the exit is activity.finish() via jnius).

NOTE: stubs below are plain classes — MagicMock auto-creates a non-None
`.content` on every attribute access, which sends
_find_immersive_player's recursive walk into infinite recursion.
"""

import asyncio
from types import SimpleNamespace
from unittest import mock

import flet as ft
import pytest

import main as main_mod
from core.state import state
from services import pip_service


@pytest.fixture(autouse=True)
def _reset_state():
    state.reset()
    yield
    state.reset()


class TestPlayStreamOwnLock:
    """play_stream must never be blocked or dropped by channel loading."""

    @pytest.mark.asyncio
    async def test_play_proceeds_while_channel_loader_holds_lock(self, fake_page):
        with mock.patch.object(main_mod, "db_manager") as db:
            db.save_history = mock.AsyncMock()
            controller = main_mod.AppController(fake_page)
            controller._loading_lock = asyncio.Lock()

            # Simulate load_all_channels mid-flight holding the loading lock
            async with controller._loading_lock:
                await controller.play_stream(
                    "http://anime.example/ep1.m3u8", None, from_deep_link=True
                )

            # Regression: the old code logged "play_stream locked, ignoring
            # duplicate request" here and returned — a permanent blank screen.
            assert any(getattr(v, "route", None) == "/play" for v in fake_page.views), (
                "deep-link play was dropped while the loader held the lock"
            )

    @pytest.mark.asyncio
    async def test_duplicate_play_suppressed_while_play_in_flight(self, fake_page):
        controller = main_mod.AppController(fake_page)
        controller._play_lock = asyncio.Lock()

        async with controller._play_lock:
            await controller.play_stream("http://tv.example/live.m3u8", None)

        assert fake_page.views == [], (
            "duplicate play must still be suppressed by _play_lock"
        )

    @pytest.mark.asyncio
    async def test_deep_link_play_marks_controller_for_exit_on_close(self, fake_page):
        with mock.patch.object(main_mod, "db_manager") as db:
            db.save_history = mock.AsyncMock()
            controller = main_mod.AppController(fake_page)
            await controller.play_stream(
                "http://anime.example/ep1.m3u8", None, from_deep_link=True
            )
            assert controller._deep_link_open is True

    @pytest.mark.asyncio
    async def test_in_app_play_does_not_mark_exit_on_close(self, fake_page):
        with mock.patch.object(main_mod, "db_manager") as db:
            db.save_history = mock.AsyncMock()
            controller = main_mod.AppController(fake_page)
            await controller.play_stream("http://tv.example/live.m3u8", None)
            assert controller._deep_link_open is False


class TestDeepLinkCloseExitsToCaller:
    def _play_view(self, player=None):
        if player is not None:
            return SimpleNamespace(route="/play", controls=[player])
        return SimpleNamespace(route="/play")

    @pytest.mark.asyncio
    async def test_close_player_saves_then_exits_when_deep_link_view_is_only_view(
        self, fake_page
    ):
        controller = main_mod.AppController(fake_page)
        controller._deep_link_open = True
        player = SimpleNamespace(
            source_url="http://anime.example/ep1.m3u8",
            _last_position=120.0,
            _last_duration=600.0,
            _is_closing=False,
            video=SimpleNamespace(playlist=[], update=lambda: None),
        )
        fake_page.views = [self._play_view(player)]

        with (
            mock.patch.object(main_mod.AppController, "_find_immersive_player") as find,
            mock.patch.object(
                pip_service, "set_auto_pip", mock.MagicMock(return_value=True)
            ),
            mock.patch.object(
                pip_service, "exit_app", mock.MagicMock(return_value=True)
            ),
            mock.patch.object(main_mod, "db_manager") as db,
        ):
            find.return_value = player
            db.update_history_position = mock.AsyncMock()
            controller._close_player()
            assert len(fake_page._run_task_calls) == 1
            fn, args, _kwargs = fake_page._run_task_calls[0]
            assert fn == controller._close_player_with_save
            # Execute the scheduled close: position saved (awaited) BEFORE
            # the activity is finished — a fire-and-forget save dies at
            # teardown, which is exactly why resume worked on desktop but
            # never on phone.
            await fn(*args)
            db.update_history_position.assert_awaited_once_with(
                "http://anime.example/ep1.m3u8", 120.0, 600.0
            )
            assert controller._deep_link_open is False

    def test_close_player_pops_normally_with_shell_beneath(self, fake_page):
        controller = main_mod.AppController(fake_page)
        controller._deep_link_open = False
        shell = SimpleNamespace(route="/")
        play_view = SimpleNamespace(route="/play")
        fake_page.views = [shell, play_view]

        controller._close_player()

        assert fake_page.views == [shell]

    @pytest.mark.asyncio
    async def test_exit_to_caller_resets_pip_and_finishes_activity(self, fake_page):
        controller = main_mod.AppController(fake_page)
        controller._deep_link_open = True

        with (
            mock.patch.object(
                pip_service, "set_auto_pip", mock.MagicMock(return_value=True)
            ) as sp,
            mock.patch.object(
                pip_service, "exit_app", mock.MagicMock(return_value=True)
            ) as ex,
        ):
            await controller._exit_to_caller()

        sp.assert_called_once_with(False)
        ex.assert_called_once()
        assert controller._deep_link_open is False

    def test_view_pop_schedules_awaited_close_not_teardown_race(self, fake_page):
        """System back must schedule _close_player_with_save (which awaits
        the position write before popping/finishing) instead of popping
        synchronously after a fire-and-forget save."""
        controller = main_mod.AppController(fake_page)
        controller._deep_link_open = True

        player = SimpleNamespace(
            source_url="http://anime.example/ep1.m3u8",
            _last_position=0.0,
            _last_duration=0.0,
            _is_closing=False,
            video=SimpleNamespace(playlist=[], update=lambda: None),
        )
        view = SimpleNamespace(route="/play", controls=[player])
        fake_page.views = [view]

        with mock.patch.object(
            main_mod.AppController, "_find_immersive_player"
        ) as find:
            find.return_value = player
            controller.view_pop(None)

        assert len(fake_page._run_task_calls) == 1
        fn, args, _kwargs = fake_page._run_task_calls[0]
        assert fn == controller._close_player_with_save
        assert args[0] is player
        # The view must still be mounted — teardown happens only AFTER the
        # awaited save inside _close_player_with_save.
        assert len(fake_page.views) == 1

    def test_view_pop_ignores_second_back_while_close_in_flight(self, fake_page):
        controller = main_mod.AppController(fake_page)
        controller._deep_link_open = True

        player = SimpleNamespace(
            source_url="http://anime.example/ep1.m3u8",
            _last_position=0.0,
            _last_duration=0.0,
            _is_closing=False,
            _position_saved=False,
            video=SimpleNamespace(playlist=[], update=lambda: None),
        )
        view = SimpleNamespace(route="/play", controls=[player])
        fake_page.views = [view]

        with mock.patch.object(
            main_mod.AppController, "_find_immersive_player"
        ) as find:
            find.return_value = player
            controller.view_pop(None)
            # First close finished its awaited save — only then is a second
            # back a no-op. Closing-but-unsaved must NOT skip the save (that
            # was the route_change/view_pop race that lost positions).
            player._position_saved = True
            controller.view_pop(None)

        assert len(fake_page._run_task_calls) == 1, (
            "double back must not schedule a second close"
        )

    def test_view_pop_does_not_double_schedule_an_in_flight_close(self, fake_page):
        """A close already in flight must not be scheduled a second time.

        `_position_saved` stays False for live streams and short playback,
        so the old guard (`closing and not saved` → schedule) let a second
        back press start a second `_close_player_with_save`; the first one
        popped /play and the second popped the dashboard underneath it.
        `_is_closing` alone means "a close task is running".
        """
        controller = main_mod.AppController(fake_page)

        player = SimpleNamespace(
            source_url="http://anime.example/ep1.m3u8",
            _last_position=120.0,
            _last_duration=600.0,
            _is_closing=True,
            _position_saved=False,
            video=SimpleNamespace(playlist=[], update=lambda: None),
        )
        view = SimpleNamespace(route="/play", controls=[player])
        fake_page.views = [SimpleNamespace(route="/", controls=[]), view]

        with mock.patch.object(
            main_mod.AppController, "_find_immersive_player"
        ) as find:
            find.return_value = player
            controller.view_pop(None)

        assert len(fake_page._run_task_calls) == 0, (
            "a second close-save was scheduled for a player already closing"
        )

    def test_view_pop_skips_when_close_already_saved(self, fake_page):
        controller = main_mod.AppController(fake_page)

        player = SimpleNamespace(
            source_url="http://anime.example/ep1.m3u8",
            _last_position=120.0,
            _last_duration=600.0,
            _is_closing=True,
            _position_saved=True,
            video=SimpleNamespace(playlist=[], update=lambda: None),
        )
        view = SimpleNamespace(route="/play", controls=[player])
        fake_page.views = [SimpleNamespace(route="/", controls=[]), view]

        with mock.patch.object(
            main_mod.AppController, "_find_immersive_player"
        ) as find:
            find.return_value = player
            controller.view_pop(None)

        assert len(fake_page._run_task_calls) == 0

    @pytest.mark.asyncio
    async def test_ktv_deep_link_appends_blank_underlay(self, fake_page):
        """The deep-linked player must never be the only view: flet's Dart
        system-back handler returns early when views.length <= 1 and exits
        the activity with no Python event at all — the resume position was
        lost. The blank underlay keeps system back on the view_pop path."""
        controller = main_mod.AppController(fake_page)
        fake_page.route = "ktv://play?url=abc123"
        fake_page.views = [SimpleNamespace(route="/")]

        with mock.patch.object(controller, "_handle_deep_link") as dl:
            await controller.route_change()

        assert state.is_deep_link_launch is True
        dl.assert_called_once_with("ktv://play?url=abc123")
        assert len(fake_page.views) == 1
        assert fake_page.views[0].route == "/blank"

    @pytest.mark.asyncio
    async def test_stop_branch_routes_through_awaited_close_save(self, fake_page):
        """Navigating away from /play must schedule the close-save (position
        persisted BEFORE playback stops), not a bare stop that marks
        _is_closing without saving."""
        controller = main_mod.AppController(fake_page)
        fake_page.route = "/"

        player = SimpleNamespace(
            source_url="http://example.com/vod.mp4",
            _last_position=120.0,
            _last_duration=600.0,
            _is_closing=False,
            _position_saved=False,
            video=SimpleNamespace(playlist=[], update=lambda: None),
        )
        shell = SimpleNamespace(route="/")
        play_view = SimpleNamespace(route="/play", controls=[player])
        fake_page.views = [shell, play_view]

        with mock.patch.object(
            main_mod.AppController, "_find_immersive_player"
        ) as find:
            find.return_value = player
            await controller.route_change()

        assert player._is_closing is True
        assert len(fake_page._run_task_calls) == 1
        fn, args, _kwargs = fake_page._run_task_calls[0]
        assert fn == controller._close_player_with_save
        assert args[0] is player
        # Teardown happens only AFTER the awaited save inside close-save.
        assert len(fake_page.views) == 2

    @pytest.mark.asyncio
    async def test_close_save_exits_to_caller_with_underlay_present(self, fake_page):
        """With the blank underlay beneath a deep-linked player, close-save
        must still exit to the caller (deep-link branch first), not pop the
        player and strand the app on the blank view."""
        controller = main_mod.AppController(fake_page)
        controller._deep_link_open = True

        player = SimpleNamespace(
            source_url="http://anime.example/ep1.m3u8",
            _last_position=120.0,
            _last_duration=600.0,
            _is_closing=True,
            _position_saved=False,
            video=SimpleNamespace(playlist=[], update=lambda: None),
        )
        blank = SimpleNamespace(route="/blank")
        play_view = SimpleNamespace(route="/play", controls=[player])
        fake_page.views = [blank, play_view]

        with (
            mock.patch.object(
                pip_service, "set_auto_pip", mock.MagicMock(return_value=True)
            ),
            mock.patch.object(
                pip_service, "exit_app", mock.MagicMock(return_value=True)
            ),
            mock.patch.object(main_mod, "db_manager") as db,
        ):
            db.update_history_position = mock.AsyncMock()
            await controller._close_player_with_save(player)

        db.update_history_position.assert_awaited_once_with(
            "http://anime.example/ep1.m3u8", 120.0, 600.0
        )
        assert controller._deep_link_open is False
        assert len(fake_page.views) == 2, "blank underlay must not be popped"


class TestLifecycleCheckpoint:
    """lifecycle 'hidden' (minimize/home) must checkpoint the top
    player's position — the exit paths flet doesn't hook."""

    def test_hidden_schedules_checkpoint_save(self, fake_page):
        controller = main_mod.AppController(fake_page)

        player = SimpleNamespace(
            source_url="http://example.com/vod.mp4",
            _last_position=120.0,
            _last_duration=600.0,
            _is_closing=False,
            video=SimpleNamespace(playlist=[], update=lambda: None),
        )
        play_view = SimpleNamespace(route="/play", controls=[player])
        fake_page.views = [SimpleNamespace(route="/blank"), play_view]

        with mock.patch.object(
            main_mod.AppController, "_find_immersive_player"
        ) as find:
            find.return_value = player
            controller._save_top_player_position()

        assert len(fake_page._run_task_calls) == 1
        fn, args, _kwargs = fake_page._run_task_calls[0]
        assert fn == controller._persist_player_position
        assert args[0] is player

    def test_hidden_skips_closing_player(self, fake_page):
        controller = main_mod.AppController(fake_page)

        player = SimpleNamespace(
            source_url="http://example.com/vod.mp4",
            _last_position=120.0,
            _last_duration=600.0,
            _is_closing=True,
            video=SimpleNamespace(playlist=[], update=lambda: None),
        )
        play_view = SimpleNamespace(route="/play", controls=[player])
        fake_page.views = [SimpleNamespace(route="/blank"), play_view]

        with mock.patch.object(
            main_mod.AppController, "_find_immersive_player"
        ) as find:
            find.return_value = player
            controller._save_top_player_position()

        assert len(fake_page._run_task_calls) == 0


class TestPeriodicPositionCheckpoint:
    """VOD-only throttled saves during playback — what makes resume survive
    Android killing the app mid-play."""

    def _player(self):
        from components.player.immersive_player import ImmersivePlayer

        return ImmersivePlayer(resource="http://example.com/vod.mp4", title="VOD")

    @pytest.mark.asyncio
    async def test_periodic_save_fires_for_vod_after_interval(self):
        from components.player import immersive_player as ip_mod

        p = self._player()
        p._last_duration = 600.0
        p._last_position = 120.0
        p._last_position_save = 0.0  # force interval elapsed

        async def _drain_orphans():
            pending = list(ip_mod._orphan_tasks)
            if pending:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True), timeout=2
                )

        upd = mock.AsyncMock()
        with mock.patch.object(ip_mod.db_manager, "update_history_position", upd):
            p._maybe_save_position_periodically()
            await _drain_orphans()
            upd.assert_awaited_once()
            # Throttled: immediate second call must not fire again
            p._maybe_save_position_periodically()
            await _drain_orphans()
            upd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_periodic_save_skips_live_and_short_positions(self):
        from components.player import immersive_player as ip_mod

        p = self._player()
        upd = mock.AsyncMock()
        with mock.patch.object(ip_mod.db_manager, "update_history_position", upd):
            # Live stream: duration 0
            p._last_duration = 0.0
            p._last_position = 50.0
            p._last_position_save = 0.0
            p._maybe_save_position_periodically()
            await asyncio.sleep(0)  # nothing scheduled; just yield
            # Meaningful progress only: position 2s
            p._last_duration = 600.0
            p._last_position = 2.0
            p._maybe_save_position_periodically()
            await asyncio.sleep(0)
            upd.assert_not_awaited()


class TestPipParamsExplicitDisable:
    """_build_params must call setAutoEnterEnabled(False) explicitly —
    skipping the setter left the Activity's previous auto-enter params
    active, so the app kept entering PiP long after playback ended."""

    @staticmethod
    def _install_bridge_mock(sdk=32):
        """Mock the android_bridge layer pip_service now delegates to."""
        builder_instance = mock.MagicMock()
        builder_cls = mock.MagicMock(return_value=builder_instance)

        def autoclass_cached(name):
            if name == "android.app.PictureInPictureParams$Builder":
                return builder_cls
            if name == "android.util.Rational":
                return mock.MagicMock()
            return mock.MagicMock()

        patches = [
            mock.patch.object(
                pip_service, "autoclass_cached", side_effect=autoclass_cached
            )
            if hasattr(pip_service, "autoclass_cached")
            else mock.patch(
                "services.android_bridge.autoclass_cached",
                side_effect=autoclass_cached,
            ),
            mock.patch.object(pip_service, "sdk_int", return_value=sdk),
        ]
        return builder_instance, patches

    def test_disable_sends_set_auto_enter_enabled_false(self):
        builder_instance, patches = self._install_bridge_mock(sdk=32)
        with patches[0], patches[1]:
            params = pip_service._build_params(auto_enter=False, aspect=16 / 9)
        builder_instance.setAutoEnterEnabled.assert_called_once_with(False)
        assert params is not None

    def test_enable_sends_set_auto_enter_enabled_true(self):
        builder_instance, patches = self._install_bridge_mock(sdk=32)
        with patches[0], patches[1]:
            pip_service._build_params(auto_enter=True, aspect=16 / 9)
        builder_instance.setAutoEnterEnabled.assert_called_once_with(True)

    def test_below_api_31_never_sets_auto_enter(self):
        builder_instance, patches = self._install_bridge_mock(sdk=30)
        with patches[0], patches[1]:
            pip_service._build_params(auto_enter=True, aspect=16 / 9)
        builder_instance.setAutoEnterEnabled.assert_not_called()


class TestExitAppHelper:
    def test_exit_app_finishes_activity(self):
        activity = mock.MagicMock()
        with mock.patch.object(pip_service, "get_activity", return_value=activity):
            assert pip_service.exit_app() is True
        activity.finish.assert_called_once()

    def test_exit_app_no_activity_returns_false(self):
        with mock.patch.object(pip_service, "get_activity", return_value=None):
            assert pip_service.exit_app() is False


class TestEventParsing:
    """flet-video 1.0.1 delivers ft.Duration, not a number.

    (Imported here so the class-level docstring reads first.)

    The old handler did `float(e.data)`, which raises TypeError for a
    Duration; a bare `except` swallowed it, so `_last_position` and
    `_last_duration` stayed at 0.0 forever — the exact `dur=0.0 pos=0.0`
    that appeared in every "position save skipped" log line on device.
    """

    @staticmethod
    def _player():
        from components.player.immersive_player import ImmersivePlayer

        return ImmersivePlayer(resource="http://example.com/vod.mp4")

    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            (ft.Duration(seconds=120), 120.0),
            (ft.Duration(minutes=9), 540.0),
            (90, 90.0),  # plain seconds pass through
            # NOTE: the old ms/us shape-guess (90000 -> 90.0) was removed:
            # flet-video 1.0.1 documents Duration payloads, and the heuristic
            # misclassified any real VOD position over 1000s (1500s -> 1.5s).
            # Raw numbers now pass through unscaled.
            (90_000, 90_000.0),
        ],
    )
    def test_event_payloads_become_seconds(self, payload, expected):
        player = self._player()
        player._overlay_hidden = True
        player._check_and_trigger_seek = lambda: None

        event = SimpleNamespace(data=payload)
        player._on_pos_change(event)
        assert player._last_position == expected

        player._on_duration_change(event)
        assert player._last_duration == expected

    def test_unusable_payloads_leave_state_untouched(self):
        player = self._player()
        player._overlay_hidden = True
        player._check_and_trigger_seek = lambda: None
        player._last_position = 7.0

        for payload in (None, "garbage", object()):
            player._on_pos_change(SimpleNamespace(data=payload))

        assert player._last_position == 7.0

    def test_a_zero_duration_is_recorded(self):
        """A reset to zero must land: the old `elif val > 0` kept the
        previous duration stale across playlist swaps."""
        player = self._player()
        player._overlay_hidden = True
        player._check_and_trigger_seek = lambda: None
        player._last_duration = 600.0

        player._on_duration_change(SimpleNamespace(data=ft.Duration(seconds=0)))

        assert player._last_duration == 0.0


class TestOnLoadReady:
    """on_load is the deterministic ready signal (watchdog/overlay/PiP/probe)."""

    def _player(self):
        from components.player.immersive_player import ImmersivePlayer

        return ImmersivePlayer(resource="http://example.com/vod.mp4", title="VOD")

    def test_on_first_ready_hides_overlay_and_arms_pip(self):
        p = self._player()
        assert p._overlay_hidden is False
        p._on_first_ready()
        assert p._overlay_hidden is True
        assert p._watchdog_task is None

    def test_on_first_ready_ignored_when_closing_or_failed(self):
        p = self._player()
        p._is_closing = True
        p._on_first_ready()
        assert p._overlay_hidden is False
        p._is_closing = False
        p._is_final_error = True
        p._on_first_ready()
        assert p._overlay_hidden is False

    def test_first_position_tick_rearms_pip_on_slow_start(self):
        p = self._player()
        p._overlay_hidden = True
        p._check_and_trigger_seek = lambda: None
        armed = []
        p._arm_auto_pip = lambda: armed.append(True)
        assert p._pip_active is False
        p._on_pos_change(SimpleNamespace(data=ft.Duration(seconds=5)))
        assert armed == [True]

    def test_zero_ticks_do_not_hide_or_arm(self):
        p = self._player()
        p._check_and_trigger_seek = lambda: None
        armed = []
        p._arm_auto_pip = lambda: armed.append(True)
        p._on_pos_change(SimpleNamespace(data=ft.Duration(seconds=0)))
        p._on_duration_change(SimpleNamespace(data=ft.Duration(seconds=0)))
        assert p._overlay_hidden is False
        assert armed == []

    @pytest.mark.asyncio
    async def test_periodic_save_wired_into_pos_change(self):
        from components.player import immersive_player as ip_mod

        p = self._player()
        p._overlay_hidden = True
        p._check_and_trigger_seek = lambda: None
        p._arm_auto_pip = lambda: None
        p._last_duration = 600.0
        p._last_position_save = 0.0
        upd = mock.AsyncMock()
        with mock.patch.object(ip_mod.db_manager, "update_history_position", upd):
            p._on_pos_change(SimpleNamespace(data=ft.Duration(seconds=120)))
            pending = list(ip_mod._orphan_tasks)
            if pending:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True), timeout=2
                )
            upd.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_bounded_when_stop_hangs(self):
        p = self._player()

        async def _hang():
            await asyncio.sleep(30)

        p.video = mock.MagicMock()
        p.video.stop = mock.AsyncMock(side_effect=_hang)
        p.video.get_current_position = mock.AsyncMock(
            return_value=ft.Duration(seconds=10)
        )
        p.video.get_duration = mock.AsyncMock(return_value=ft.Duration(seconds=100))
        p.source_url = "http://example.com/vod.mp4"

        await asyncio.wait_for(p.handle_close(), timeout=10.0)
        assert p._is_closing is True

    def test_unmount_skips_save_after_close(self):
        from components.player import immersive_player as ip_mod

        p = self._player()
        p._position_saved = True
        p.source_url = "http://example.com/vod.mp4"
        p._last_duration = 600.0
        p._last_position = 120.0
        upd = mock.AsyncMock()
        with mock.patch.object(ip_mod.db_manager, "update_history_position", upd):
            p.will_unmount()
            upd.assert_not_awaited()

    def test_video_defaults_low_and_desktop_bg_flags(self):
        """Restored v2.2.0 values: filter_quality LOW (the MEDIUM change
        was an unverified 'guidance' claim) and the desktop background
        flags pause=True / resume=False. _sync_background_flags() runs in
        __init__ so the values no longer depend on _arm/_disarm, which
        early-return without PiP and left desktop unsynced."""
        p = self._player()
        assert p.video.filter_quality == ft.FilterQuality.LOW
        assert p.video.pause_upon_entering_background_mode is True
        assert p.video.resume_upon_entering_foreground_mode is False

    def test_volume_clamped(self):
        from components.player.immersive_player import ImmersivePlayer

        assert ImmersivePlayer(resource="u", volume=150.0).video.volume == 100.0
        assert ImmersivePlayer(resource="u", volume=-5.0).video.volume == 0.0


class TestLifecycleStateDispatch:
    """Phase 3: save on e.state HIDE/PAUSE/DETACH (not dead e.data)."""

    def _controller_with_lifecycle(self, fake_page):
        controller = main_mod.AppController(fake_page)
        # Minimal init surface for the lifecycle closure: attach the handler
        # the same way init() does, without the full init().
        page = fake_page
        _controller = controller
        _previous = page.on_app_lifecycle_state_change

        def _on_lifecycle_save(e):
            import flet as _ft

            if getattr(e, "state", None) in (
                _ft.AppLifecycleState.HIDE,
                _ft.AppLifecycleState.PAUSE,
                _ft.AppLifecycleState.DETACH,
            ):
                _controller._save_top_player_position()
            if getattr(e, "state", None) in (
                _ft.AppLifecycleState.RESUME,
                _ft.AppLifecycleState.SHOW,
            ):
                pass
            if _previous is not None:
                _previous(e)

        page.on_app_lifecycle_state_change = _on_lifecycle_save
        return controller

    def test_hide_state_saves_not_data(self, fake_page):
        from types import SimpleNamespace as _NS

        self._controller_with_lifecycle(fake_page)
        player = _NS(
            source_url="http://example.com/vod.mp4",
            _last_position=120.0,
            _last_duration=600.0,
            _is_closing=False,
            video=_NS(playlist=[], update=lambda: None),
        )
        play_view = _NS(route="/play", controls=[player])
        fake_page.views = [_NS(route="/blank"), play_view]
        with mock.patch.object(
            main_mod.AppController, "_find_immersive_player"
        ) as find:
            find.return_value = player
            import flet as _ft

            # e.state HIDE (no e.data at all on 1.0.1) must save.
            fake_page.on_app_lifecycle_state_change(
                _NS(state=_ft.AppLifecycleState.HIDE)
            )
        assert len(fake_page._run_task_calls) == 1

    def test_garbage_event_saves_nothing(self, fake_page):
        from types import SimpleNamespace as _NS

        self._controller_with_lifecycle(fake_page)
        fake_page.views = [_NS(route="/blank")]
        with mock.patch.object(
            main_mod.AppController, "_find_immersive_player"
        ) as find:
            find.return_value = None
            import flet as _ft

            fake_page.on_app_lifecycle_state_change(
                _NS(state=_ft.AppLifecycleState.INACTIVE)
            )
        assert len(fake_page._run_task_calls) == 0


class TestFallbackUnderlay:
    """Phase 3: /?url= fallback leaves [blank, play] like ktv://."""

    @pytest.mark.asyncio
    async def test_fallback_appends_blank_underlay(self, fake_page):
        controller = main_mod.AppController(fake_page)
        fake_page.route = "/?url=aHR0cHM6Ly9leGFtcGxlLmNvbS9zLm0zdTg=&title=VGVzdA=="
        with mock.patch.object(controller, "_handle_deep_link", return_value=None):
            await controller.route_change()
        routes = [getattr(v, "route", "") for v in fake_page.views]
        assert routes[0] == "/blank"
