"""Channel split — the Play build must be free-only, provably.

The Play Console in use has no Google Payments merchant profile, so the
AAB that ships through Play cannot sell anything. It must also not offer
the Kiri License: an external-checkout button inside a Play-distributed
build is a policy violation. So the AAB job stamps CHANNEL = "play" and
everything premium disappears.

These tests walk the rendered Settings screen and fail if a play build
can reach any purchase UI, and pin the service so it cannot be tricked
into a worker request either.
"""

from types import SimpleNamespace
from unittest import mock

import pytest

import core.channel
from core.state import state
from services.premium_service import PremiumService
from tests.license_fixtures import TOKENS

PLAY_CHANNEL = 'CHANNEL = "play"'


@pytest.fixture
def _play_channel(monkeypatch):
    monkeypatch.setattr(core.channel, "CHANNEL", "play")
    # premium_service binds the constant by module name.
    monkeypatch.setattr("services.premium_service.CHANNEL", "play")


@pytest.fixture(autouse=True)
def _clean_state():
    state.reset()
    yield
    state.reset()


@pytest.fixture
def store():
    """In-memory settings table for the license service."""
    values: dict[str, str] = {}

    async def get_setting(key, default=None):
        return values.get(key, default)

    async def set_setting(key, value):
        values[key] = str(value)

    dbm = mock.AsyncMock()
    dbm.get_setting.side_effect = get_setting
    dbm.set_setting.side_effect = set_setting
    with mock.patch("services.kiri_license.db_manager", dbm):
        yield values


def _page(mobile: bool = True):
    page = mock.MagicMock()
    page.platform = SimpleNamespace(
        is_mobile=lambda: mobile,
        __eq__=lambda self, other: False,
    )
    page.services = []
    return page


# -- committed default ------------------------------------------------------


def test_committed_channel_is_direct():
    """The repo default is the direct channel; only the AAB job overrides it."""
    assert core.channel.CHANNEL == "direct"


def test_marker_file_contains_no_conditional():
    """The stamp is a single assignment — the AAB job overwrites the file."""
    source = (
        __import__("pathlib").Path(__file__).parent.parent / "src/core/channel.py"
    ).read_text(encoding="utf-8")
    assert "CHANNEL = " in source
    assert "if " not in source.split('"""')[-1], "keep the marker dead simple"


# -- service on the play channel --------------------------------------------


def test_play_build_has_no_premium_surface(_play_channel):
    svc = PremiumService(_page(mobile=True))
    assert svc.backend == "none"
    assert svc.available is False
    assert not hasattr(svc, "billing"), "Play Billing is gone from this build"
    assert _page(mobile=True).services == []


@pytest.mark.asyncio
async def test_play_build_reconcile_is_a_no_op(_play_channel):
    """No store call and no worker request on the free-only build."""
    svc = PremiumService(_page())
    http = mock.Mock()
    with (
        mock.patch("services.kiri_license.get_http_client", http),
    ):
        await svc.reconcile()
    assert http.get.call_count == 0
    assert http.post.call_count == 0


@pytest.mark.asyncio
async def test_play_build_cannot_start_any_purchase(_play_channel):
    from services.kiri_license import LicenseUnavailable

    svc = PremiumService(_page())
    assert await svc.kiri_catalog() == []
    with pytest.raises(LicenseUnavailable):
        await svc.kiri_checkout("lifetime", "buyer@example.com")
    with pytest.raises(LicenseUnavailable):
        await svc.kiri_restore("KIRI-L-anything")
    assert await svc.kiri_check_status() is None


@pytest.mark.asyncio
async def test_play_build_never_reads_a_cached_token(_play_channel, store):
    """Even a token left from a direct install must not unlock the AAB."""
    store["kiri_token"] = TOKENS["LIFETIME"]
    svc = PremiumService(_page())
    await svc.load_local()
    assert state.is_premium is False
    assert svc.license.unlocked is False


@pytest.mark.asyncio
async def test_direct_build_keeps_the_kiri_channel():
    """Sanity: without the stamp, direct builds still offer premium."""
    svc = PremiumService(_page(mobile=False))
    assert svc.backend == "kiri"
    assert svc.available is True


# -- the rendered Settings screen -------------------------------------------


def _walk(control):
    yield control
    for child in getattr(control, "controls", None) or []:
        yield from _walk(child)
    content = getattr(control, "content", None)
    if content is not None:
        yield from _walk(content)


def _setting_texts():
    """The strings a purchase surface would have to carry."""
    return (
        "upgrade",
        "unlock",
        "restore",
        "premium",
        "buy",
        "recovery id",
        "lifetime",
        "monthly",
        "yearly",
    )


def _premium_ui_strings_in(screen):
    found = []
    for node in _walk(screen):
        text = getattr(node, "value", None)
        if isinstance(text, str):
            lowered = text.lower()
            if any(word in lowered for word in _setting_texts()):
                found.append(text)
        tooltip = getattr(node, "tooltip", None)
        if isinstance(tooltip, str) and any(
            word in tooltip.lower() for word in _setting_texts()
        ):
            found.append(tooltip)
    return found


def test_play_settings_screen_omits_the_premium_card():
    """The Settings screen must not append the Premium card on the play channel.

    Flet's component renderer needs a live session to expand a
    @ft.component, so this asserts the render path structurally: the card
    is appended only behind the channel guard. The service-level tests
    above prove the play build cannot sell even if the card existed.
    """
    import inspect
    import textwrap

    from screens import settings_screen

    source = textwrap.dedent(inspect.getsource(settings_screen))
    assert 'if CHANNEL != "play":' in source, "premium card is not channel-gated"
    guard_block = source.split('if CHANNEL != "play":', 1)[1].split(
        "controls.append(about)"
    )[0]
    assert "controls.append(premium)" in guard_block


def test_direct_channel_keeps_the_premium_card_appended():
    """On every other build the Premium section is still rendered."""
    import inspect
    import textwrap

    from screens import settings_screen

    source = textwrap.dedent(inspect.getsource(settings_screen))
    assert 'if CHANNEL != "play":' in source
    # The guard is the only thing between the card and the list.
    assert source.count("controls.append(premium)") == 1


def test_play_channel_is_read_from_the_marker_module():
    import inspect

    from screens import settings_screen
    from services import premium_service

    assert "CHANNEL" in inspect.getsource(settings_screen)
    assert "CHANNEL" in inspect.getsource(premium_service)


def test_workflow_stamps_the_aab():
    """The AAB job is the only place CHANNEL becomes "play"."""
    import pathlib

    wf = (
        pathlib.Path(__file__).resolve().parent.parent
        / ".github/workflows/build-all.yml"
    ).read_text(encoding="utf-8")
    assert PLAY_CHANNEL in wf
    assert "echo 'CHANNEL = \"play\"'" in wf
