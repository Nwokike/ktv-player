"""Tests for the focus_scope component (FocusScope alias)."""

from unittest import mock

import flet as ft
import pytest

from hooks.use_focus_scope import _BACK_KEYS, FocusScope, focus_scope


def _fire(scope, event):
    """Fire a key event at the scope. The listener sits inside the expanding
    Container (see the layout test below), so unwrap to reach on_key_down."""
    listener = scope.content if isinstance(scope, ft.Container) else scope
    return listener.on_key_down(event)


def test_focus_scope_expands_its_wrapper_container():
    """The player View mounts FocusScope directly, so the wrapper — not the
    listener — is what hands the player Stack its bounds. Dropping it is the
    white-player-with-audio regression: Flet's KeyboardListener is a bare
    Control (not a LayoutControl), so `expand=True` on it is ignored and the
    Stack underneath sizes to zero. The listener keeps autofocus so Back
    delivery never depends on which button holds focus.
    """
    scope = FocusScope(child=ft.Text("hi"))
    assert isinstance(scope, ft.Container)
    assert scope.expand is True
    listener = scope.content
    assert isinstance(listener, ft.KeyboardListener)
    assert listener.autofocus is True
    assert isinstance(listener.content, ft.Text)


def test_keyboard_listener_is_not_a_layout_control():
    """Pins WHY the wrapper exists rather than looking redundant.

    Verified against
    .venv/Lib/site-packages/flet/controls/core/keyboard_listener.py: the
    class extends Control, so Flet's renderer never expands it and the
    inherited `expand` field is inert. Constructing one with expand=True
    succeeds silently, which is exactly why this regression was invisible.
    """
    assert not issubclass(ft.KeyboardListener, ft.LayoutControl)
    assert issubclass(ft.Container, ft.LayoutControl)
    listener = ft.KeyboardListener(content=ft.Text("x"), expand=True)
    assert listener.expand is True


def test_focus_scope_passes_child_through():
    text = ft.Text("hi")
    scope = FocusScope(child=text)
    assert scope.content.content is text


def test_back_keys_verified_set():
    assert frozenset({"Back", "Escape", "BrowserBack"}) == _BACK_KEYS
    assert focus_scope is FocusScope


@pytest.mark.anyio
async def test_on_back_fires_for_back_key():
    received = []
    scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
    fake_event = mock.Mock()
    fake_event.key = "Back"
    await _fire(scope, fake_event)
    assert received == [fake_event]


@pytest.mark.anyio
async def test_on_back_fires_for_escape():
    received = []
    scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
    fake_event = mock.Mock()
    fake_event.key = "Escape"
    await _fire(scope, fake_event)
    assert received == [fake_event]


@pytest.mark.anyio
async def test_on_back_fires_for_browser_back():
    received = []
    scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
    fake_event = mock.Mock()
    fake_event.key = "BrowserBack"
    await _fire(scope, fake_event)
    assert received == [fake_event]


@pytest.mark.anyio
async def test_on_back_does_not_fire_for_arrow_keys():
    received = []
    for key in ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Tab"]:
        fake_event = mock.Mock()
        fake_event.key = key
        scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
        await _fire(scope, fake_event)
    assert received == []


@pytest.mark.anyio
async def test_on_back_optional_works_without_handler():
    """If on_back is None, back keys fall through silently (Flutter handles)."""
    fake_event = mock.Mock()
    fake_event.key = "Back"
    scope = FocusScope(child=ft.Text("x"))  # no on_back
    await _fire(scope, fake_event)  # must not raise


@pytest.mark.anyio
async def test_on_back_exception_does_not_propagate():
    """A raising on_back is logged, not propagated into event dispatch."""

    def _boom(e):
        raise RuntimeError("close I/O failed")

    fake_event = mock.Mock()
    fake_event.key = "Escape"
    scope = FocusScope(child=ft.Text("x"), on_back=_boom)
    await _fire(scope, fake_event)  # must not raise
