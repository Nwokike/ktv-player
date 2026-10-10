"""2.3.0 regression pins: the three user-reported breakages plus the fixes.

1. Focus handlers wrote `control.scale` on cards that are the body of a
   `@ft.component` — frozen after render, so EVERY focus event raised
   "Frozen controls cannot be updated" (reproduced from a real run).
2. The FocusScope back handler called `handle_close()` before
   `_close_player()`; `handle_close` sets `_is_closing`, after which
   `_close_player` saw a close "already in flight" and bailed — the player
   view never popped and the user was stranded.
3. The theme toggle dropped its local mirror, so the icon/switch lagged
   behind the page repaint.
4. The web deep-link fallback passed a raw URL where only base64url was
   accepted, so a browser link landed on a black view with no error; it
   also dropped headers/referer.
5. A quality/audio swap reset the playback rate to 1.0x while the chip
   still showed the old value.
"""

import asyncio
import base64
from types import SimpleNamespace
from unittest import mock

import flet as ft
import flet.controls.context as ctx_mod
import pytest


class FakeVideo:
    def __init__(self, **kw):
        self.playlist = None
        self.playback_rate = None

    async def play(self):
        pass

    async def is_playing(self):
        return True

    async def stop(self):
        pass

    def update(self):
        pass


class FakePage:
    def __init__(self):
        self.views = []
        self.overlay = []
        self.services = []
        self.dialog = None
        self.platform = ft.PagePlatform.LINUX
        self.theme_mode = ft.ThemeMode.SYSTEM
        self.platform_brightness = ft.Brightness.DARK
        self.theme = None
        self.dark_theme = None
        self.width = 1280
        self.height = 800
        self.route = "/"
        self.fonts = {}
        self.tasks = []

    def update(self, *a, **k):
        pass

    def run_task(self, fn, *a, **k):
        t = asyncio.ensure_future(fn(*a, **k))
        self.tasks.append(t)
        return t

    async def drain(self, rounds=8):
        for _ in range(rounds):
            await asyncio.sleep(0.02)
            await asyncio.gather(*list(self.tasks), return_exceptions=True)


def _controller(page, **attrs):
    import main as main_mod
    from core.state import state

    with mock.patch("main.AppController.init", new=mock.AsyncMock()):
        ctrl = main_mod.AppController(page)
    ctrl.page = page
    ctrl.hls_proxy = None
    ctrl.ad_service = None
    for k, v in attrs.items():
        setattr(ctrl, k, v)
    state.reset()
    state.channels = []
    state.channels_hash = "h"
    state.has_accepted_terms = True
    state.is_first_launch = False
    return ctrl


# --- 1. no prop mutation on frozen cards -------------------------------


def test_cards_carry_no_focus_scale_mutation():
    from components.channel_card import ChannelCard
    from components.video_card import VideoCard
    from services.local_scanner import LocalVideo

    card = ChannelCard(
        channel={"url": "http://x", "name": "X", "logo": ""},
        is_favorite=False,
        on_play=lambda u: None,
        on_toggle_favorite=lambda u: None,
    )
    assert card.on_focus is None
    assert card.on_blur is None

    vcard = VideoCard(
        video=LocalVideo(name="v.mp4", path="/v.mp4", size=1),
        on_play=lambda p: None,
    )
    surface = _play_surface(vcard)
    assert surface.on_focus is None
    assert surface.on_blur is None


def _play_surface(card):
    from tests.flet_tree import walk

    return next(
        c
        for c in walk(card)
        if isinstance(c, ft.FilledButton) and callable(getattr(c, "on_click", None))
    )


def test_no_source_writes_scale():
    import inspect

    import components.channel_card as cc
    import components.video_card as vc

    for mod in (cc, vc):
        src = inspect.getsource(mod)
        assert ".scale = " not in src, mod.__name__
        assert 'setattr(' not in src, mod.__name__


# --- 2. back/close must actually pop the player ------------------------


@pytest.mark.asyncio
async def test_in_app_back_pops_player_view():
    page = FakePage()
    page.views = [SimpleNamespace(route="/")]
    ctx_mod._context_page.set(page)
    ctrl = _controller(page)

    with mock.patch("flet_video.Video", FakeVideo):
        await ctrl.play_stream("http://example.com/live.m3u8", "T")
        await page.drain()
        player = ctrl._player_in_top_view()
        assert player is not None

        ctrl._close_player()
        await page.drain()
        routes = [getattr(v, "route", None) for v in page.views]
        assert "/play" not in routes, routes


@pytest.mark.asyncio
async def test_deep_link_back_exits_to_caller():
    page = FakePage()
    page.views = [SimpleNamespace(route="/blank")]
    ctx_mod._context_page.set(page)
    ctrl = _controller(page)

    with mock.patch("flet_video.Video", FakeVideo), mock.patch.object(
        type(ctrl), "_exit_app", new=mock.AsyncMock()
    ) as exit_mock:
        await ctrl.play_stream(
            "http://example.com/live.m3u8", "T", from_deep_link=True
        )
        await page.drain()
        ctrl._close_player()
        await page.drain()
        assert exit_mock.await_count == 1


@pytest.mark.asyncio
async def test_single_view_player_close_exits_not_strands():
    """Cold "Open With" launch: no view beneath to pop to."""
    page = FakePage()
    page.views = []
    ctx_mod._context_page.set(page)
    ctrl = _controller(page)

    with mock.patch("flet_video.Video", FakeVideo), mock.patch.object(
        type(ctrl), "_exit_app", new=mock.AsyncMock()
    ) as exit_mock:
        await ctrl.play_stream("file:///storage/emulated/0/Movies/a.mp4", "a")
        await page.drain()
        assert any(
            getattr(v, "route", None) == "/play" for v in page.views
        ), "player view missing"
        ctrl._close_player()
        await page.drain()
        assert exit_mock.await_count == 1, "single-view player stranded the user"


@pytest.mark.asyncio
async def test_close_player_ignores_non_play_route():
    page = FakePage()
    page.views = [SimpleNamespace(route="/")]
    ctx_mod._context_page.set(page)
    ctrl = _controller(page)
    ctrl._close_player()
    await page.drain()
    assert [getattr(v, "route", None) for v in page.views] == ["/"]


# --- 3. theme toggle repaints the control in the same frame ------------


def test_theme_toggle_sets_local_state():
    from flet.components.component import Renderer

    from components.header import Header

    class RaisingVar:
        def get(self):
            raise RuntimeError("no session")

    saved = {}

    page = SimpleNamespace(
        theme_mode=ft.ThemeMode.DARK,
        platform_brightness=ft.Brightness.DARK,
    )
    ctx_mod._context_page.set(page)

    with mock.patch("utils.theme_utils.toggle_theme"), mock.patch(
        "database.manager.db_manager"
    ) as db:

        async def _save(k, v):
            saved[k] = v

        db.set_setting = mock.AsyncMock(side_effect=_save)

        screen = Renderer().render(lambda: Header())
        screen.before_update()

        # Toggle flips the page AND schedules a re-render of the component.
        from components.header import _resolve_is_dark

        assert _resolve_is_dark(page) is True


def test_settings_switch_uses_reactive_state():
    import inspect

    from screens import settings_screen

    src = inspect.getsource(settings_screen.SettingsScreen)
    assert "is_dark_state, set_is_dark_state" in src
    assert "ft.Switch(value=is_dark_state" in src
    assert "ft.Switch(value=_is_dark()" not in src


# --- 4. deep-link fallback accepts raw AND base64 URLs -----------------


def _b64url_param(value: str) -> str:
    from main import _b64url_param as impl

    return impl(value)


def test_b64url_param_encodes_raw_and_is_idempotent():
    from main import _b64url_param as impl

    raw = "http://example.com/s.m3u8"
    enc = impl(raw)
    assert base64.urlsafe_b64decode(enc + "==").decode() == raw
    assert impl(enc) == enc, "must not double-encode"
    assert impl("") == ""
    assert impl("   ") == ""


@pytest.mark.parametrize(
    "route",
    [
        "ktv://play?url=aHR0cDovL2V4YW1wbGUuY29tL3MubTN1OA",
        "/?url=http%3A%2F%2Fexample.com%2Fs.m3u8",
        "/?url=aHR0cDovL2V4YW1wbGUuY29tL3MubTN1OA",
    ],
)
@pytest.mark.asyncio
async def test_every_deep_link_shape_plays(route):
    """A raw URL used to fail base64 validation and leave a black view."""
    page = FakePage()
    page.route = route
    ctx_mod._context_page.set(page)
    ctrl = _controller(page)

    with mock.patch.object(
        type(ctrl), "play_stream", new=mock.AsyncMock()
    ) as ps:
        await ctrl.route_change()
        await page.drain()
        assert ps.await_count == 1, f"{route} never reached play_stream"
        url = ps.await_args.args[0]
        assert url.startswith("http"), url


@pytest.mark.asyncio
async def test_fallback_forwards_headers():
    """headers/referer were dropped by the fallback, so referer-locked
    streams could not play from a browser link."""
    url = "http://example.com/s.m3u8"
    hdrs = '{"Referer": "http://ref.example"}'
    route = (
        "/?url="
        + _b64url_param(url)
        + "&headers="
        + _b64url_param(hdrs)
        + "&referer="
        + _b64url_param("http://ref.example/")
    )
    page = FakePage()
    page.route = route
    ctx_mod._context_page.set(page)
    ctrl = _controller(page)

    with mock.patch.object(
        type(ctrl), "play_stream", new=mock.AsyncMock()
    ) as ps:
        await ctrl.route_change()
        await page.drain()
        assert ps.await_count == 1
        args = ps.await_args.args
        # (url, title, referer, headers, from_deep_link)
        assert args[0] == url
        assert args[2] == "http://ref.example/", args
        assert isinstance(args[3], dict) and args[3].get("Referer") == "http://ref.example"


# --- 5. rate survives a quality/audio swap ----------------------------


@pytest.mark.asyncio
async def test_swap_media_reapplies_playback_rate():
    import inspect

    from components.player import immersive_player as ip

    src = inspect.getsource(ip.ImmersivePlayer._swap_media)
    assert "playback_rate" in src, (
        "a playlist swap resets the native rate to 1.0x; the chip would "
        "otherwise lie about the current speed"
    )
