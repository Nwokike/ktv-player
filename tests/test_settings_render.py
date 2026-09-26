"""The Settings tab must actually render for a free user.

`SettingsScreen` builds a Kiri row when the catalog has not loaded yet
(products start empty), and that row once omitted the required `trailing`
argument. The body raised TypeError on the very first render, Flet's
update scheduler swallowed it, and the tab came up blank with no log line.

`Renderer().render()` alone does NOT run the body — it builds the wrapper
node — so this test calls `before_update()`, which is what actually
executes the component function (flet/components/component.py).
"""

from flet.components.component import Renderer

import core.channel
from core.state import state


class _Platform:
    def is_mobile(self):
        return True

    def is_desktop(self):
        return True


class _Page:
    def __init__(self):
        self.platform = _Platform()
        self.services = []
        self.views = []
        self.route = "/"
        self.theme_mode = None
        self.title = ""
        self.premium = None

    def update(self, *a, **k):
        pass

    def schedule_update(self, *a, **k):
        pass

    def run_task(self, fn, *args, **kwargs):
        return None

    def show_dialog(self, *a, **k):
        pass

    def pop_dialog(self, *a, **k):
        pass

    @property
    def session(self):
        raise RuntimeError("no session in tests")


def _render(monkeypatch, *, premium, is_premium=False, channel="direct"):
    from flet.controls.context import _context_page

    from screens.settings_screen import SettingsScreen

    page = _Page()
    page.premium = premium
    _context_page.set(page)
    monkeypatch.setattr(core.channel, "CHANNEL", channel)
    monkeypatch.setattr("screens.settings_screen.CHANNEL", channel)
    state.is_premium = is_premium
    state.has_accepted_terms = True
    state.is_first_launch = False

    screen = Renderer().render(SettingsScreen)
    # This is what actually executes the body — render() only wraps it,
    # and the produced tree is stashed on `_b` (the body's return value).
    screen.before_update()
    return screen


def _count_and_collect(control):
    # The body's output lives on `_b`; the wrapper node itself is childless.
    control = getattr(control, "_b", control) or control
    nodes, texts = 1, []

    def walk(node):
        nonlocal nodes
        for child in getattr(node, "controls", None) or []:
            nodes += 1
            if isinstance(getattr(child, "value", None), str):
                texts.append(child.value)
            walk(child)
        content = getattr(node, "content", None)
        if content is not None:
            nodes += 1
            if isinstance(getattr(content, "value", None), str):
                texts.append(content.value)
            walk(content)

    walk(control)
    return nodes, texts


def test_free_user_renders_the_full_screen(monkeypatch):
    """The regression: a non-premium user must not raise."""
    screen = _render(monkeypatch, premium=None, is_premium=False)
    nodes, texts = _count_and_collect(screen)
    # Vacuous-render guard: the false pass earlier reported ~1 node.
    assert nodes > 20, f"body did not execute (nodes={nodes})"
    assert any("Premium" in t for t in texts), texts[:10]


def test_premium_user_renders(monkeypatch):
    screen = _render(monkeypatch, premium=None, is_premium=True)
    nodes, texts = _count_and_collect(screen)
    assert nodes > 20
    assert any("Ads removed" in t for t in texts)


def test_play_channel_builds_the_kiri_rows_without_raising(monkeypatch):
    """The rows were assembled outside the CHANNEL guard, so the Play AAB
    hit the same TypeError even though the card was discarded."""
    screen = _render(monkeypatch, premium=None, is_premium=False, channel="play")
    nodes, texts = _count_and_collect(screen)
    assert nodes > 20, "play build must still render settings"
    assert not any("Unlock options" in t for t in texts)


def test_setting_row_accepts_a_missing_trailing():
    """Direct guard for the argument that blanked the tab."""
    import flet as ft

    from screens.settings_screen import _setting_row

    row = _setting_row(
        leading=ft.Icon(ft.Icons.INFO),
        title="t",
        subtitle="s",
    )
    assert row is not None


def test_contact_and_rate_rows_use_the_device_guard():
    """Phones and TV rate on the Play Store; everything else stars GitHub."""
    import inspect
    from unittest import mock

    import flet as ft

    from core.constants import GITHUB_REPO_URL, PLAY_STORE_URL
    from screens.settings_screen import SettingsScreen, _rate_subtitle, _rate_url

    def page_on(platform):
        page = mock.Mock()
        page.platform = platform
        return page

    assert _rate_url(page_on(ft.PagePlatform.ANDROID)) == PLAY_STORE_URL
    assert _rate_url(page_on(ft.PagePlatform.IOS)) == PLAY_STORE_URL
    assert _rate_url(page_on(ft.PagePlatform.ANDROID_TV)) == PLAY_STORE_URL
    assert _rate_url(page_on(ft.PagePlatform.WINDOWS)) == GITHUB_REPO_URL
    assert _rate_url(page_on(ft.PagePlatform.LINUX)) == GITHUB_REPO_URL
    assert "Google Play" in _rate_subtitle(page_on(ft.PagePlatform.ANDROID_TV))
    assert "GitHub" in _rate_subtitle(page_on(ft.PagePlatform.WINDOWS))

    src = inspect.getsource(SettingsScreen)
    assert "Contact developer" in src
    assert "mailto:" in src and "CONTACT_EMAIL" in src
    assert "Rate 5 stars" in src
    # The address itself lives in constants, referenced by name.
    from core import constants as core_constants

    assert core_constants.CONTACT_EMAIL == "hello@kiri.ng"
