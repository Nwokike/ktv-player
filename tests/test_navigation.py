"""Phase 3 — view-stack navigation contract tests.

Covers: history overlay dup guard, View appbar slot + leading back,
tab bounds, declarative nav bar ownership, shell-view fallback removal.
"""

from unittest import mock

import flet as ft

from src.main import AppController


def _page():
    page = mock.MagicMock()
    page.views = []
    page.route = "/"
    return page


class TestCloseGuardPredicate:
    def test_close_already_saved_needs_both_flags(self):
        player = mock.MagicMock()
        player._is_closing = True
        player._position_saved = True
        assert AppController._close_already_saved(player) is True

    def test_closing_without_save_is_not_done(self):
        """Live/short playback: _position_saved False must NOT skip close."""
        player = mock.MagicMock()
        player._is_closing = True
        player._position_saved = False
        assert AppController._close_already_saved(player) is False

    def test_idle_player_is_not_done(self):
        player = mock.MagicMock()
        player._is_closing = False
        player._position_saved = False
        assert AppController._close_already_saved(player) is False

    def test_missing_attrs_default_false(self):
        from types import SimpleNamespace

        # MagicMock auto-creates truthy children, so a bare object proves
        # the getattr defaults.
        assert AppController._close_already_saved(SimpleNamespace()) is False


class TestBlankUnderlayHelper:
    def test_push_blank_underlay_appends_black_view(self):
        page = _page()
        controller = AppController(page)
        controller._push_blank_underlay()
        assert len(page.views) == 1
        assert page.views[0].route == "/blank"


class TestViewPopOverlay:
    def test_view_pop_closes_history_overlay(self):
        from types import SimpleNamespace

        page = _page()
        controller = AppController(page)
        # SimpleNamespace views: MagicMock auto-creates infinite .content /
        # .controls chains that recurse forever in _find_immersive_player.
        page.views = [
            SimpleNamespace(route="/", controls=[]),
            SimpleNamespace(route="/recently-watched", controls=[]),
        ]
        controller._deep_link_open = False
        controller.view_pop(mock.MagicMock())
        assert len(page.views) == 1
        assert page.views[0].route == "/"
        page.update.assert_called()


class TestTabBounds:
    def test_tab_names_count(self):
        from src.app_shell import _TAB_NAMES

        assert len(_TAB_NAMES) == 3

    def test_shell_view_helper_removed(self):
        """The fragile route-allowlist search is gone (replaced by the
        _ShellNavigationBar component owning views[0])."""
        import src.app_shell as shell_mod

        assert not hasattr(shell_mod, "_shell_view")
        assert hasattr(shell_mod, "_ShellNavigationBar")


class TestHistoryScreenProps:
    def test_screen_accepts_on_back_and_page(self):
        import inspect

        from src.screens.recently_watched_screen import RecentlyWatchedScreen

        params = inspect.signature(RecentlyWatchedScreen).parameters
        assert "on_back" in params
        assert "page" in params

    def test_empty_state_has_browse_cta(self):
        from src.screens.recently_watched_screen import RecentlyWatchedScreen

        backs = []
        body = RecentlyWatchedScreen(
            history=[],
            channels_map={},
            on_play=lambda u, t=None: None,
            on_back=lambda: backs.append(True),
        )
        # Walk the tree for the CTA button.
        found = []

        def _walk(c):
            text = getattr(getattr(c, "content", None), "value", "")
            if isinstance(c, ft.FilledButton) and text == "Browse channels":
                found.append(c)
            for child in (getattr(c, "controls", None) or []) + (
                [getattr(c, "content", None)] if getattr(c, "content", None) else []
            ):
                if isinstance(child, ft.Control):
                    _walk(child)

        _walk(body)
        assert found, "empty history must offer a Browse channels CTA"
        found[0].on_click(mock.MagicMock())
        assert backs == [True]

    def test_legacy_string_entry_renders(self):
        """One legacy plain-string entry must not crash the list."""
        from src.screens.recently_watched_screen import RecentlyWatchedScreen

        body = RecentlyWatchedScreen(
            history=["http://example.com/old.m3u8"],
            channels_map={},
            on_play=lambda u, t=None: None,
        )
        assert body is not None
