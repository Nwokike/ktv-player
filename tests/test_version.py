"""Phase 7 — version dialog + add-content + filter/header contract tests."""

from types import SimpleNamespace
from unittest import mock

import flet as ft
import pytest


@pytest.fixture
def page_ctx():
    """OpenUrl binds the shared UrlLauncher at construction, so button
    tests need a page in context (production always has one)."""
    import flet.controls.context as ctx_mod

    token = ctx_mod._context_page.set(mock.Mock())
    yield
    ctx_mod._context_page.reset(token)


# --- version dialog ---


def test_is_launchable_url_gates_schemes():
    from components.version_dialog import is_launchable_url

    assert is_launchable_url("https://github.com/x") is True
    assert is_launchable_url("http://x") is True
    assert is_launchable_url("mailto:a@b.c") is True
    assert is_launchable_url("market://details?id=x") is True
    assert is_launchable_url("") is False
    assert is_launchable_url(None) is False
    assert is_launchable_url("javascript:alert(1)") is False
    assert is_launchable_url("ftp://x") is False
    assert is_launchable_url("  ") is False


def test_update_buttons_use_open_url_action(page_ctx):
    """Buttons open in-gesture (never popup-blocked) + dismiss on click."""
    from components.version_dialog import _build_update_buttons

    page = SimpleNamespace(platform=ft.PagePlatform.WINDOWS)
    buttons = _build_update_buttons(page, {"github_url": "https://g.example/r"})
    filled = next(b for b in buttons if isinstance(b, ft.FilledButton))
    assert isinstance(filled.action, ft.OpenUrl)
    assert filled.action.url == "https://g.example/r"
    assert callable(filled.on_click)


def test_update_buttons_android_tv_github_only(page_ctx):
    """TV has no Play listing: GitHub APK only, never the Play button."""
    from components.version_dialog import _build_update_buttons

    page = SimpleNamespace(platform=ft.PagePlatform.ANDROID_TV)
    buttons = _build_update_buttons(
        page, {"playstore_url": "https://play.example", "github_url": "https://g/x"}
    )
    labels = [b.content.value for b in buttons if hasattr(b.content, "value")]
    assert not any("Google Play" in label for label in labels)
    assert any("GitHub" in label for label in labels)


def test_update_buttons_android_play_plus_apk(page_ctx):
    from components.version_dialog import _build_update_buttons

    page = SimpleNamespace(platform=ft.PagePlatform.ANDROID)
    buttons = _build_update_buttons(
        page, {"playstore_url": "https://play.example", "github_url": "https://g/x"}
    )
    labels = [b.content.value for b in buttons if hasattr(b.content, "value")]
    assert any("Google Play" in label for label in labels)
    assert any("Direct APK" in label for label in labels)


def test_mandatory_has_no_later_button(page_ctx):
    from components.version_dialog import _build_update_buttons

    page = SimpleNamespace(platform=ft.PagePlatform.WINDOWS)
    buttons = _build_update_buttons(page, {"mandatory": True})
    labels = [b.content.value for b in buttons if hasattr(b.content, "value")]
    assert "Later" not in labels
    buttons = _build_update_buttons(page, {})
    labels = [b.content.value for b in buttons if hasattr(b.content, "value")]
    assert "Later" in labels


def test_dialog_width_clamps_narrow_windows():
    from components.version_dialog import _dialog_width

    assert _dialog_width(SimpleNamespace(width=360)) < 360
    assert _dialog_width(SimpleNamespace(width=1920)) == 360
    assert _dialog_width(SimpleNamespace(width=None)) == 360


def test_show_version_dialog_reuses_open_instance(page_ctx, monkeypatch):
    """A second open while one is showing reuses, never stacks.

    Off-session the reuse-update raises (no real page), so the dialog
    falls back to a fresh instance — but it must still never stack two
    visible dialogs at once.
    """
    import components.version_dialog as vd

    shown = []

    page = SimpleNamespace(
        platform=ft.PagePlatform.WINDOWS,
        width=800,
        show_dialog=lambda d: shown.append(d),
        pop_dialog=lambda: shown.pop() if shown else None,
    )
    monkeypatch.setattr(vd, "_open_dialog", None)
    vd.show_version_dialog(page)
    assert vd._open_dialog is not None
    assert len(shown) == 1
    # Simulate a mounted dialog: give the tracked instance an update().
    vd._open_dialog.update = lambda *a, **k: None
    vd.show_version_dialog(page)
    assert len(shown) == 1, "second open must reuse, not stack"
    monkeypatch.setattr(vd, "_open_dialog", None)


# --- add-content dialog ---


def test_default_playlist_name_from_url():
    from components.add_custom_content_dialog import _default_playlist_name

    assert _default_playlist_name("https://x.com/sports.m3u8") == "sports"
    assert _default_playlist_name("https://x.com/a/b/News.M3U") == "News"
    assert _default_playlist_name("https://x.com/") == "Playlist"
    assert _default_playlist_name("not a url at all") == "not a url at all"


def test_is_valid_url_parses_host():
    from components.add_custom_content_dialog import _is_valid_url

    assert _is_valid_url("https://example.com/list.m3u8") is True
    assert _is_valid_url("http://example.com") is True
    assert _is_valid_url("http://") is False
    assert _is_valid_url("https://") is False
    assert _is_valid_url("example.com/list.m3u") is False
    assert _is_valid_url("ftp://example.com/x") is False


def test_cooldown_hint_counts_down():
    import time

    from components.add_custom_content_dialog import (
        ADD_CONTENT_COOLDOWN,
        _cooldown_hint,
    )

    assert _cooldown_hint(0.0) == ""
    assert "Wait" in _cooldown_hint(time.time())
    assert _cooldown_hint(time.time() - ADD_CONTENT_COOLDOWN - 5) == ""


def test_add_dialog_source_contract():
    """Pin the structural fixes: no dead cooldown reset, awaited on_added,
    ref-based guards, named playlist, inline errors, hook order."""
    import inspect

    from components import add_custom_content_dialog as dlg

    src = inspect.getsource(dlg.AddCustomContentDialog)
    assert "set_last_add(0.0)" not in src
    assert "await result" in src
    assert "asyncio.create_task(result)" not in src
    assert "use_ref" in src
    assert "_default_playlist_name" in src
    assert '"Playlist", final_url' not in src
    # Inline field error. Flet 1.0.1 TextField has NO error_text — the
    # kwarg is `error` (verified against the installed package); using
    # error_text raised TypeError on every render when open.
    assert "error=" in src and "error_text=" not in src
    # Hooks before any branch: first use_* call precedes `if open:`.
    first_hook = min(
        src.find("ft.use_state"), src.find("ft.use_ref"), src.find("ft.use_context")
    )
    assert first_hook < src.find("if open:")
    # on_dismiss takes the event.
    assert "on_dismiss=lambda e:" in src


# --- filter bar ---


def test_filter_bar_source_contract():
    """Pin Phase 7 FilterBar fixes without mounting the component."""
    import inspect

    from components import filter_bar

    src = inspect.getsource(filter_bar)
    assert 'current_country != "all"' in src  # predicate, not default-country
    assert '"All Countries"' in src
    assert '"All Categories"' in src
    assert "checked=" in src
    assert "casefold" in src
    assert "Icons.ADD" in src
    assert "total_count" in src  # accepted...


def test_filter_bar_renders_checked_items(monkeypatch):
    """checked= marks the active item in each menu.

    PopupMenuItems live on the button's `.items` (not in the control
    tree), so the walk covers both.
    """
    import flet.controls.context as ctx_mod

    class _RaisingVar:
        def get(self):
            raise RuntimeError("no session")

    monkeypatch.setattr(ctx_mod, "_context_page", _RaisingVar())
    from flet.components.component import Renderer

    from components.filter_bar import FilterBar

    screen = Renderer().render(
        lambda: FilterBar(
            filters={"country": "Nigeria", "category": "all", "custom": "none"},
            on_change=lambda p: None,
            available_countries=["Nigeria", "Ghana"],
            available_categories=["Sports"],
            user_country="Other",
        )
    )
    screen.before_update()
    body = getattr(screen, "_b", screen)

    def _walk(node):
        yield node
        for item in getattr(node, "items", None) or []:
            yield from _walk(item)
        for child in getattr(node, "controls", None) or []:
            yield from _walk(child)
        content = getattr(node, "content", None)
        if content is not None:
            yield from _walk(content)

    checked = [n for n in _walk(body) if isinstance(n, ft.PopupMenuItem) and n.checked]
    assert checked, "no checked item rendered"
