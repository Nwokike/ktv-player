"""Tests for notification routing: SnackBar normally, in-controls chip in fullscreen."""

import asyncio
from unittest import mock

import pytest

from utils import notifications


class TestFullscreenToastRouting:
    def _register(self):
        container, text = mock.MagicMock(), mock.MagicMock()
        notifications.register_fullscreen_toast(container, text)
        return container, text

    def teardown_method(self):
        notifications.unregister_fullscreen_toast()

    def test_chip_untouched_when_not_fullscreen(self):
        container, text = self._register()
        notifications.set_fullscreen_toast_active(False)
        notifications.notify("plain message")
        assert text.value != "plain message"
        assert container.visible is not True

    def test_chip_shown_when_fullscreen_active(self):
        container, text = self._register()
        notifications.set_fullscreen_toast_active(True)
        try:
            notifications.notify_warning("stream is offline")
            assert text.value == "stream is offline"
            assert container.visible is True
            container.update.assert_called()
        finally:
            notifications.set_fullscreen_toast_active(False)

    def test_exit_fullscreen_hides_chip(self):
        container, _text = self._register()
        notifications.set_fullscreen_toast_active(True)
        notifications.notify("bye")
        notifications.set_fullscreen_toast_active(False)
        assert container.visible is False

    def test_unregister_clears_registration(self):
        self._register()
        notifications.set_fullscreen_toast_active(True)
        notifications.unregister_fullscreen_toast()
        assert notifications._fullscreen_toast["container"] is None
        assert notifications._fullscreen_toast["text"] is None
        assert notifications._fullscreen_toast["active"] is False

    def test_notify_after_unregister_does_not_crash(self):
        notifications.unregister_fullscreen_toast()
        notifications.notify("no chip registered")

    @pytest.mark.asyncio
    async def test_chip_auto_hides(self, monkeypatch):
        monkeypatch.setattr(notifications, "_TOAST_HIDE_AFTER", 0.05)
        container, _text = self._register()
        notifications.set_fullscreen_toast_active(True)
        notifications.notify("fade away")
        await asyncio.sleep(0.15)
        assert container.visible is False
        notifications.set_fullscreen_toast_active(False)
