"""Tests for the FocusScope component."""

from unittest import mock

import flet as ft
import pytest

from app_next.hooks.use_focus_scope import FocusScope


def test_focus_scope_returns_keyboard_listener_with_child():
    scope = FocusScope(child=ft.Text("hi"))
    assert isinstance(scope, ft.KeyboardListener)
    assert isinstance(scope.content, ft.Text)


def test_focus_scope_passes_child_through():
    text = ft.Text("hi")
    scope = FocusScope(child=text)
    assert scope.content is text


@pytest.mark.anyio
async def test_on_back_fires_for_back_key():
    received = []
    fake_event = mock.Mock()
    fake_event.key = "Back"

    scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
    await scope.on_key_down(fake_event)
    assert received == [fake_event]


@pytest.mark.anyio
async def test_on_back_fires_for_escape():
    received = []
    fake_event = mock.Mock()
    fake_event.key = "Escape"

    scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
    await scope.on_key_down(fake_event)
    assert received == [fake_event]


@pytest.mark.anyio
async def test_on_back_fires_for_browser_back():
    received = []
    fake_event = mock.Mock()
    fake_event.key = "BrowserBack"

    scope = FocusScope(child=ft.Text("x"), on_back=lambda e: received.append(e))
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
