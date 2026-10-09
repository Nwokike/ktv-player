"""Phase 8 verification-swarm regression tests.

Every test here pins a defect found by the independent release audit
(Oct 2026). Each was verified against installed sources before the fix;
these assert the FIXED contract so the bugs cannot silently return.
"""

import asyncio
import inspect
import re
import time
from types import SimpleNamespace
from unittest import mock

import flet as ft
import pytest

# ---------------------------------------------------------------------------
# state.set_channels — order-sensitive hash
# ---------------------------------------------------------------------------


def test_channels_hash_is_order_sensitive():
    """sorted() canonicalized order, so a reordered playlist kept the same
    hash and every memo kept serving the old order."""
    from core.state import state

    state.reset()
    a = {"url": "http://a", "group": "G", "country": "c", "name": "A"}
    b = {"url": "http://b", "group": "G", "country": "c", "name": "B"}
    state.set_channels([a, b])
    first = state.channels_hash
    state.set_channels([b, a])
    assert state.channels_hash != first
    state.reset()


def test_channels_hash_empty_stays_empty_string():
    from core.state import state

    state.reset()
    state.set_channels([])
    assert state.channels_hash == ""
    state.reset()


def test_channels_hash_ignores_non_dict_rows():
    from core.state import state

    state.reset()
    state.set_channels(["junk", {"url": "http://a"}, 42])
    assert state.channels_hash  # still computed from the one good row
    state.reset()


# ---------------------------------------------------------------------------
# anyio_pools — drain race + orphaned getters
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pool_drains_item_arriving_with_stop():
    """An item that lands just as stop fires must still be processed."""
    from services.anyio_pools import TaskPool

    processed = []
    gate = asyncio.Event()

    async def worker(item):
        gate.set()
        await asyncio.sleep(0.01)
        processed.append(item)

    pool = TaskPool("t", worker, workers=1, queue_max=10)
    pool.ensure_started()
    assert pool.submit("first") is True
    await gate.wait()  # worker busy on "first"
    assert pool.submit("second") is True  # queued
    await pool.stop(drain=True)
    assert sorted(processed) == ["first", "second"], processed


@pytest.mark.asyncio
async def test_pool_cancel_leaves_no_orphan_getters():
    """A worker cancelled mid-wait must not leave queue._getters behind."""
    from services.anyio_pools import TaskPool

    started = asyncio.Event()

    async def worker(item):
        started.set()
        await asyncio.sleep(30)

    pool = TaskPool("t", worker, workers=1)
    pool.ensure_started()
    pool.submit("x")
    await started.wait()
    # Sync emergency stop (liveliness/logo shutdown_workers path).
    pool._supervisor.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pool._supervisor
    queue = pool._queue
    assert queue is not None
    await asyncio.sleep(0.02)
    assert not queue._getters, f"orphaned getters: {queue._getters}"


@pytest.mark.asyncio
async def test_pool_re_enqueue_after_emergency_stop_works():
    """After an emergency stop, items must not be swallowed by dead getters."""
    from services.anyio_pools import TaskPool

    processed = []

    async def worker(item):
        processed.append(item)

    pool = TaskPool("t", worker, workers=1, queue_max=5)
    pool.ensure_started()
    pool.submit("a")
    await pool.stop(drain=True)
    # A fresh pool on the same queue shape must still process normally.
    pool2 = TaskPool("t", worker, workers=1, queue_max=5)
    pool2.ensure_started()
    assert pool2.submit("b") is True
    await pool2.stop(drain=True)
    assert processed == ["a", "b"]


# ---------------------------------------------------------------------------
# liveliness_checker — _in_flight leak
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_flight_cleared_after_probe():
    """_in_flight was never discarded on completion: after TTL expiry the
    URL could never be re-enqueued — dots went permanently stale."""
    from services import liveliness_checker as lc

    lc.state.is_online = True
    lc._in_flight.clear()

    async def fake_check_single(url):
        return (url, True)

    lc.LivelinessChecker = lambda _: SimpleNamespace(
        check_single=fake_check_single
    )
    lc.drain_queue()
    await lc._probe_and_persist("http://probe.example/v")
    assert "http://probe.example/v" not in lc._in_flight
    lc.drain_queue()


@pytest.mark.asyncio
async def test_in_flight_cleared_after_cancelled_probe():
    """Same leak on the cancellation path."""
    from services import liveliness_checker as lc

    lc._in_flight.clear()

    async def fake_check_single(url):
        raise asyncio.CancelledError

    lc.LivelinessChecker = lambda _: SimpleNamespace(
        check_single=fake_check_single
    )
    with pytest.raises(asyncio.CancelledError):
        await lc._probe_and_persist("http://cancel.example/v")
    assert "http://cancel.example/v" not in lc._in_flight


# ---------------------------------------------------------------------------
# url_validator — protocol-relative + case
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("//evil.com/stream", False),
        ("/", False),
        ("///", False),
        ("C:/", False),
        ("/home/user/video.mp4", True),
        ("C:/Videos/movie.mp4", True),
        ("D:\\Videos\\movie.mp4", True),
    ],
)
def test_path_branch_acceptance(url, expected):
    """//evil.com is a protocol-relative network ref, not a local file;
    bare roots are not media."""
    from core.url_validator import is_valid_play_url

    assert is_valid_play_url(url) is expected


def test_file_scheme_case_insensitive():
    from core.url_validator import is_valid_play_url

    assert is_valid_play_url("FILE:///sdcard/Movies/v.mp4") is True
    assert is_valid_play_url("Content://media/video/file.mp4") is True


def test_deeplink_header_padded_blocked_key_dropped():
    """Padded " Authorization " used to slip the blocklist (compared
    unstripped) and was stored under the stripped name."""
    import base64

    from core.deeplink import parse_deep_link

    url_b64 = base64.urlsafe_b64encode(b"http://x.test/s.m3u8").rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        b'{" Authorization ": "Bearer x", "X-Ok": "fine"}'
    ).rstrip(b"=").decode()
    route = f"ktv://play?url={url_b64}&headers={payload}"
    url, _, _, headers = parse_deep_link(route)
    # url, title, referer, headers
    assert url == "http://x.test/s.m3u8"
    assert headers is not None
    assert "Authorization" not in headers, headers
    # The benign header still arrives.
    assert "X-Ok" in headers


# ---------------------------------------------------------------------------
# http_client — transport-level knobs
# ---------------------------------------------------------------------------


def test_http2_and_limits_are_on_the_transport():
    """A custom transport= drops client-level http2=/limits=; they must be
    passed to AsyncHTTPTransport or both are silently dead."""
    import inspect

    from services.http_client import _build_client

    src = inspect.getsource(_build_client)
    # Both knobs must sit on the transport construction, not the client.
    assert "AsyncHTTPTransport(" in src
    assert "http2=True" in src
    assert "limits=limits" in src
    # And the client must not ALSO declare them (dead config).
    body = src.split("return httpx.AsyncClient(", 1)[1]
    client_kwargs = body.split("transport=", 1)[0]
    assert "http2=" not in client_kwargs
    assert "limits=" not in client_kwargs


def test_no_brotli_in_accept_encoding():
    """brotli isn't installed: advertising br and receiving it silently
    returned compressed bytes (no decoder -> identity fallback)."""
    from services.http_client import _build_client

    client = _build_client()
    ae = client.headers.get("accept-encoding", "").lower()
    assert "br" not in ae


# ---------------------------------------------------------------------------
# core/state controls — single-parent + branch text updates
# ---------------------------------------------------------------------------


def test_speed_chip_builds_fresh_text_per_branch():
    """The same shared speed Text got TWO parents when mobile and desktop
    both built — Flet single-parent rule violation."""
    from components.player.controls import _make_speed_chip

    inst = SimpleNamespace(speed_available=True, page=SimpleNamespace())
    _make_speed_chip(inst)
    t1 = inst.speed_text
    _make_speed_chip(inst)  # second branch
    assert inst.speed_text is not t1, "speed Text must be fresh per branch"
    texts = inst.speed_texts
    assert len(texts) == 2


@pytest.mark.asyncio
async def test_cycle_speed_updates_every_branch():
    import types

    from components.player import handlers
    from components.player.immersive_player import ImmersivePlayer

    player = mock.AsyncMock()
    player._speed_idx = 2
    player._speeds = [0.25, 0.5, 1.0, 1.25, 1.5, 2.0]
    player.video = mock.MagicMock()
    t1, t2 = mock.MagicMock(), mock.MagicMock()
    player.speed_text = t1
    player.speed_texts = [t1, t2]
    player._branch_controls = types.MethodType(
        ImmersivePlayer._branch_controls, player
    )
    await handlers.cycle_speed(player)
    # EVERY branch's text updates, not just the singular.
    assert t1.value == "1.25x"
    assert t2.value == "1.25x"


# ---------------------------------------------------------------------------
# app_loader — timeout zip + cancellation + isolation
# ---------------------------------------------------------------------------


def test_app_loader_timeout_keeps_length_alignment():
    """A 60s fan-out timeout built fetched_lists=[] and then zip(...,
    strict=True) against a non-empty active_playlists — ValueError on the
    empty-channels path, which is exactly the offline case."""
    import inspect

    from core import app_loader

    src = inspect.getsource(app_loader)
    assert "fetched_lists = [[] for _ in active_playlists]" in src


def test_app_loader_propagates_cancellation():
    import inspect

    from core import app_loader

    src = inspect.getsource(app_loader)
    # Cancellation must reach the OUTER handler before its generic ones:
    # the last except block (state.set_channels path) re-raises it.
    idx_cancel = src.rfind("except asyncio.CancelledError")
    idx_generic = src.rfind("except Exception:")
    assert idx_cancel != -1 and idx_cancel < idx_generic


def test_app_loader_isolates_unexpected_fetch_errors():
    """_safe_fetch only caught PlaylistFetchError: any other exception
    aborted the whole fan-out and dropped already-merged channels."""
    import inspect

    from core import app_loader

    src = inspect.getsource(app_loader)
    # Two warn/return paths inside _safe_fetch (typed + unexpected).
    body = src[src.find("async def _safe_fetch") :]
    assert body.count("return []") >= 2


# ---------------------------------------------------------------------------
# dialogs — search border kwargs, add-content error kwarg, Wrap removal
# ---------------------------------------------------------------------------


def test_search_field_uses_valid_outline_border_kwargs():
    """radius=/border_side= do not exist on OutlineInputBorder — the
    search screen never rendered."""
    import inspect

    from screens import search_screen

    src = inspect.getsource(search_screen)
    assert re.search(r"(?<!_)radius=14", src) is None
    assert "border_radius=14" in src
    assert "border_side=" not in src


def test_folder_tile_uses_wrapping_row():
    """ft.Wrap does not exist in Flet 1.0.1 — every folder expansion
    crashed."""
    import inspect

    from components import folder_expansion_tile

    src = inspect.getsource(folder_expansion_tile)
    assert "ft.Wrap(" not in src
    assert "ft.Row(" in src and "wrap=True" in src


def test_add_content_dialog_uses_error_not_error_text():
    import inspect

    from components import add_custom_content_dialog as dlg

    src = inspect.getsource(dlg.AddCustomContentDialog)
    assert "error_text=" not in src
    assert "error=url_error" in src


def test_page_close_does_not_exist_replaced_with_pop():
    """page.close(dialog) is not a Flet 1.0.1 API — every settings-dialog
    close threw AttributeError into the fallback."""
    import inspect

    from components.player import handlers

    src = inspect.getsource(handlers)
    assert ".page.close(" not in src
    assert "pop_dialog()" in src


def test_file_picker_request_bytes_for_web():
    """without_data, FilePickerFile.bytes is always None — the web
    subtitle path was dead code."""
    import inspect

    from components.player import handlers

    src = inspect.getsource(handlers)
    assert "with_data=True" in src


def test_safe_variant_and_audio_return_none():
    """The sentinels leaked into _current_variant, which then hit
    f\"V{self._current_variant + 1}\" -> TypeError, and built a proxy URL
    with variant=\"auto\"."""
    import inspect

    from components.player import handlers

    src = inspect.getsource(handlers)
    safe_variant = src[src.find("def _safe_variant") : src.find("def _safe_audio")]
    safe_audio = src[src.find("def _safe_audio") :]
    assert 'return "auto"' not in safe_variant
    assert 'return "default"' not in safe_audio
    assert "return None" in safe_variant and "return None" in safe_audio


# ---------------------------------------------------------------------------
# controller_ctx — noop signature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noop_update_check_accepts_keyword():
    """The fixed-signature default rejected notify_if_latest= with a
    TypeError — the contract says defaults never TypeError."""
    from state.controller_ctx import ControllerMethods

    m = ControllerMethods()
    await m.check_for_updates(notify_if_latest=True)  # must not raise
    await m.check_for_updates(True)


# ---------------------------------------------------------------------------
# nav bar — view targeting after /blank underlay
# ---------------------------------------------------------------------------


def test_dashboard_view_skips_blank_and_play():
    """/blank is INSERTED at views[0], pushing the dashboard to index 1+;
    views[0] was the invisible underlay."""
    from app_shell import _dashboard_view

    blank = SimpleNamespace(route="/blank")
    dash = SimpleNamespace(route="/")
    play = SimpleNamespace(route="/play")
    page = SimpleNamespace(views=[blank, dash, play])
    assert _dashboard_view(page) is dash
    page2 = SimpleNamespace(views=[dash])
    assert _dashboard_view(page2) is dash
    page3 = SimpleNamespace(views=[])
    assert _dashboard_view(page3) is None


def test_shell_mutates_controller_instance():
    """dataclasses.replace left AppController holding the DEFAULT methods,
    so Back on a non-Home tab exited the app instead of returning Home."""
    import inspect

    from app_shell import AppShell

    src = inspect.getsource(AppShell)
    # Only the explanatory comment may mention it; no live call.
    live = chr(10).join(
        line for line in src.splitlines() if not line.strip().startswith("#")
    )
    assert "dataclasses.replace" not in live
    assert "controller.go_home = _go_home" in src
    assert "controller.on_non_home_tab = _on_non_home_tab" in src


# ---------------------------------------------------------------------------
# normalize — acronym preservation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("USA", "USA"),
        ("UK", "UK"),
        ("U.S. Virgin Islands", "U.S. Virgin Islands"),
        ("Nigeria", "Nigeria"),
        ("nigeria", "Nigeria"),
        ("NIGERIA", "Nigeria"),
    ],
)
def test_canonical_country_preserves_acronyms(raw, expected):
    from channels.normalize import _canonical_country

    assert _canonical_country(raw) == expected, raw


# ---------------------------------------------------------------------------
# msgpack corruption paths
# ---------------------------------------------------------------------------


def test_truncated_msgpack_falls_back_to_empty(tmp_path, monkeypatch):
    """OutOfData/BufferFull are NOT ValueError subclasses — a truncated
    snapshot crashed load_cache instead of falling back."""

    import services.liveliness_store as ls

    monkeypatch.setattr(ls, "STORE_PATH", str(tmp_path / "l.mpk"))
    good = {"http://a": [True, time.time()]}
    ls._write(good)
    # truncate mid-payload
    with open(ls.STORE_PATH, "rb") as f:
        raw = f.read()
    with open(ls.STORE_PATH, "wb") as f:
        f.write(raw[: len(raw) // 2])
    from services.liveliness_store import _read

    assert _read() is None


def test_sidecar_truncated_returns_none(tmp_path):
    from channels.sidecar import load_sidecar, store_sidecar

    raw = tmp_path / "p.m3u8"
    raw.write_text("#EXTM3U\n", encoding="utf-8")
    channels = [
        {k: (f"{k}{i}" if i == 0 else "x") for k in
         ("url", "name", "logo", "group", "country", "country_code")}
        for i in range(2)
    ]
    # Add the remaining fields so the tuple matches _FIELDS length
    full = []
    for c in channels:
        full.append({
            "url": c["url"], "name": c["name"], "logo": c["logo"],
            "group": c["group"], "country": c["country"],
            "country_code": c["country_code"], "categories": [],
            "tvg_id": "", "tvg_country": "", "is_custom": False,
        })
    store_sidecar(str(raw), full)
    with open(str(raw) + ".mpk", "rb") as f:
        data = f.read()
    with open(str(raw) + ".mpk", "wb") as f:
        f.write(data[: len(data) // 2])
    assert load_sidecar(str(raw)) is None


# ---------------------------------------------------------------------------
# local_scanner — MediaStore columns + folder grouping
# ---------------------------------------------------------------------------


def test_mediastore_projection_uses_real_column_names():
    """"_display_name" is the real MediaColumns.DISPLAY_NAME value;
    "display_name" threw getColumnIndexOrThrow and emptied the library."""
    import inspect

    from services import local_scanner

    src = inspect.getsource(local_scanner)
    scan_src = src[src.find("def scan_android_mediastore") :]
    assert '"display_name"' not in scan_src
    assert '"_display_name"' in scan_src


def test_id_only_rows_share_one_folder():
    """Per-URI folder keys made N single-video folders."""
    import inspect

    from services import local_scanner

    src = inspect.getsource(local_scanner)
    assert "mediastore:device-videos" in src
    assert "f\"mediastore:{vid.content_uri}\"" not in src


# ---------------------------------------------------------------------------
# theme — contrast claim honesty
# ---------------------------------------------------------------------------


def test_theme_secondary_comment_matches_measured_contrast():
    """The old comment claimed black 'fails contrast' — measurement says
    white 4.10:1 vs black 5.13:1 on #0284C7."""
    from core.theme import AppTheme

    dark = AppTheme.get_dark_theme()
    src = inspect.getsource(AppTheme.get_dark_theme)
    assert "4.10" in src and "5.13" in src
    assert dark.color_scheme.on_secondary == ft.Colors.WHITE


# ---------------------------------------------------------------------------
# misc one-liners
# ---------------------------------------------------------------------------


def test_immersive_player_await_helper_for_run_task():
    """page.run_task(lambda: result) violates the iscoroutinefunction
    requirement — the coroutine would be silently dropped."""
    import inspect

    from components.player import immersive_player

    src = inspect.getsource(immersive_player)
    assert "page.run_task(lambda: result)" not in src
    assert "_await_result" in src


def test_changelog_normalize_roundtrip():
    from core.changelog import CHANGELOG, notes_for
    from core.constants import APP_VERSION

    assert notes_for(f"v{APP_VERSION}") == CHANGELOG[APP_VERSION]
    assert notes_for(f"  {APP_VERSION} ") == CHANGELOG[APP_VERSION]
    # Unknown version falls back to the NEWEST entry, not the oldest.
    assert notes_for("0.0.0") == CHANGELOG[APP_VERSION]


def test_state_reset_clears_deep_link_flag():
    from core.state import state

    state.is_deep_link_launch = True
    state.reset()
    assert state.is_deep_link_launch is False


def test_liveliness_store_fsyncs(tmp_path, monkeypatch):
    import inspect

    import services.liveliness_store as ls

    src = inspect.getsource(ls._write)
    assert "fsync" in src
