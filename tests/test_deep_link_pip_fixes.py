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
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

import main as main_mod
import services.pip_service as pip_service
from core.state import state


@pytest.fixture(autouse=True)
def _reset_state():
    state.reset()
    yield
    state.reset()


class TestPlayStreamOwnLock:
    """play_stream must never be blocked or dropped by channel loading."""

    @pytest.mark.asyncio
    async def test_play_proceeds_while_channel_loader_holds_lock(
        self, fake_page
    ):
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
            assert any(
                getattr(v, "route", None) == "/play" for v in fake_page.views
            ), "deep-link play was dropped while the loader held the lock"

    @pytest.mark.asyncio
    async def test_duplicate_play_suppressed_while_play_in_flight(
        self, fake_page
    ):
        controller = main_mod.AppController(fake_page)
        controller._play_lock = asyncio.Lock()

        async with controller._play_lock:
            await controller.play_stream("http://tv.example/live.m3u8", None)

        assert fake_page.views == [], (
            "duplicate play must still be suppressed by _play_lock"
        )

    @pytest.mark.asyncio
    async def test_deep_link_play_marks_controller_for_exit_on_close(
        self, fake_page
    ):
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
            mock.patch.object(
                main_mod.AppController, "_find_immersive_player"
            ) as find,
            mock.patch.object(
                pip_service, "set_auto_pip", mock.MagicMock(return_value=True)
            ),
            mock.patch.object(
                pip_service, "exit_app", mock.MagicMock(return_value=True)
            ),
            mock.patch.object(
                main_mod, "db_manager"
            ) as db,
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
    async def test_exit_to_caller_resets_pip_and_finishes_activity(
        self, fake_page
    ):
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

    def test_view_pop_schedules_awaited_close_not_teardown_race(
        self, fake_page
    ):
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

    def test_view_pop_ignores_second_back_while_close_in_flight(
        self, fake_page
    ):
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
            controller.view_pop(None)

        assert len(fake_page._run_task_calls) == 1, (
            "double back must not schedule a second close"
        )


class TestPeriodicPositionCheckpoint:
    """VOD-only throttled saves during playback — what makes resume survive
    Android killing the app mid-play."""

    def _player(self):
        from components.player.immersive_player import ImmersivePlayer

        return ImmersivePlayer(
            resource="http://example.com/vod.mp4", title="VOD"
        )

    @pytest.mark.asyncio
    async def test_periodic_save_fires_for_vod_after_interval(self):
        from components.player import immersive_player as ip_mod

        p = self._player()
        p._last_duration = 600.0
        p._last_position = 120.0
        p._last_position_save = 0.0  # force interval elapsed

        upd = mock.AsyncMock()
        with mock.patch.object(ip_mod.db_manager, "update_history_position", upd):
            p._maybe_save_position_periodically()
            await asyncio.sleep(0.05)
            upd.assert_awaited_once()
            # Throttled: immediate second call must not fire again
            p._maybe_save_position_periodically()
            await asyncio.sleep(0.05)
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
            await asyncio.sleep(0.05)
            # Meaningful progress only: position 2s
            p._last_duration = 600.0
            p._last_position = 2.0
            p._maybe_save_position_periodically()
            await asyncio.sleep(0.05)
            upd.assert_not_awaited()


class TestPipParamsExplicitDisable:
    """_build_params must call setAutoEnterEnabled(False) explicitly —
    skipping the setter left the Activity's previous auto-enter params
    active, so the app kept entering PiP long after playback ended."""

    @staticmethod
    def _install_jnius_mock():
        builder_instance = mock.MagicMock()
        builder_cls = mock.MagicMock(return_value=builder_instance)

        def autoclass(name):
            if name == "android.app.PictureInPictureParams$Builder":
                return builder_cls
            return mock.MagicMock()

        jnius = mock.MagicMock()
        jnius.autoclass = autoclass
        return builder_instance, jnius

    def test_disable_sends_set_auto_enter_enabled_false(self):
        builder_instance, jnius = self._install_jnius_mock()
        with (
            mock.patch.dict(sys.modules, {"jnius": jnius}),
            mock.patch.object(pip_service, "api_level", return_value=32),
        ):
            params = pip_service._build_params(auto_enter=False, aspect=16 / 9)
        builder_instance.setAutoEnterEnabled.assert_called_once_with(False)
        assert params is not None

    def test_enable_sends_set_auto_enter_enabled_true(self):
        builder_instance, jnius = self._install_jnius_mock()
        with (
            mock.patch.dict(sys.modules, {"jnius": jnius}),
            mock.patch.object(pip_service, "api_level", return_value=32),
        ):
            pip_service._build_params(auto_enter=True, aspect=16 / 9)
        builder_instance.setAutoEnterEnabled.assert_called_once_with(True)

    def test_below_api_31_never_sets_auto_enter(self):
        builder_instance, jnius = self._install_jnius_mock()
        with (
            mock.patch.dict(sys.modules, {"jnius": jnius}),
            mock.patch.object(pip_service, "api_level", return_value=30),
        ):
            pip_service._build_params(auto_enter=True, aspect=16 / 9)
        builder_instance.setAutoEnterEnabled.assert_not_called()


class TestExitAppHelper:
    def test_exit_app_finishes_activity(self):
        activity = mock.MagicMock()
        with mock.patch.object(
            pip_service, "_get_activity", return_value=activity
        ):
            assert pip_service.exit_app() is True
        activity.finish.assert_called_once()

    def test_exit_app_no_activity_returns_false(self):
        with mock.patch.object(pip_service, "_get_activity", return_value=None):
            assert pip_service.exit_app() is False
