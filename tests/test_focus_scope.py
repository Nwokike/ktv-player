"""Tests for the focus_scope component (FocusScope alias)."""

from unittest import mock

import flet as ft
import pytest

from hooks.use_focus_scope import _BACK_KEYS, FocusScope, focus_scope


def _fire(scope, key):
    fake_event = mock.Mock()
    fake_event.key = key
    return scope.on_key_down(fake_event)


def test_focus_scope_returns_keyboard_listener_with_autofocus():
    """Listener owns focus (autofocus) and expand directly — no wrapper."""
    scope = FocusScope(child=ft.Text("hi"))
    assert isinstance(scope, ft.KeyboardListener)
    assert scope.autofocus is True
    assert isinstance(scope.content, ft.Text)


def test_focus_scope_passes_child_through():
    text = ft.Text("hi")
    scope = FocusScope(child=text)
    assert scope.content is text


def test_back_keys_verified_set():
    assert frozenset({"Back", "Escape", "BrowserBack"}) == _BACK_KEYS
    assert focus_scope is FocusScope


@pytest.mark.anyio
async def test_on_back_fires_for_back_key():
    received = []
    scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
    fake_event = mock.Mock()
    fake_event.key = "Back"
    await scope.on_key_down(fake_event)
    assert received == [fake_event]


@pytest.mark.anyio
async def test_on_back_fires_for_escape():
    received = []
    scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
    fake_event = mock.Mock()
    fake_event.key = "Escape"
    await scope.on_key_down(fake_event)
    assert received == [fake_event]


@pytest.mark.anyio
async def test_on_back_fires_for_browser_back():
    received = []
    scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
    fake_event = mock.Mock()
    fake_event.key = "BrowserBack"
    await scope.on_key_down(fake_event)
    assert received == [fake_event]


@pytest.mark.anyio
async def test_on_back_does_not_fire_for_arrow_keys():
    received = []
    for key in ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Enter", "Tab"]:
        fake_event = mock.Mock()
        fake_event.key = key
        scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
        await scope.on_key_down(fake_event)
    assert received == []


@pytest.mark.anyio
async def test_on_back_optional_works_without_handler():
    """If on_back is None, back keys fall through silently (Flutter handles)."""
    fake_event = mock.Mock()
    fake_event.key = "Back"
    scope = FocusScope(child=ft.Text("x"))  # no on_back
    await scope.on_key_down(fake_event)  # must not raise


@pytest.mark.anyio
async def test_on_back_exception_does_not_propagate():
    """A raising on_back is logged, not propagated into event dispatch."""

    def _boom(e):
        raise RuntimeError("close I/O failed")

    fake_event = mock.Mock()
    fake_event.key = "Escape"
    scope = FocusScope(child=ft.Text("x"), on_back=_boom)
    await scope.on_key_down(fake_event)  # must not raise
