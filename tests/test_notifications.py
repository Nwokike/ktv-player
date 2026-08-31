"""Tests for notification routing: in-player chip while a player is mounted,
SnackBar elsewhere and for persistent warnings.

The chip is active from register_fullscreen_toast (player mount) — NOT from
the enter_fullscreen event. Gating on that event was the phone-fullscreen
bug: when the event doesn't fire on a platform, dispatch fell back to a
SnackBar, which the opaque fullscreen route covers — the user saw nothing.
"""

import asyncio
from unittest import mock

import pytest

from utils import notifications


class TestToastChipRouting:
    def _register(self):
        container, text = mock.MagicMock(), mock.MagicMock()
        notifications.register_fullscreen_toast(container, text)
        return container, text

    def teardown_method(self):
        notifications.unregister_fullscreen_toast()

    def test_register_activates_chip_without_fullscreen_event(self):
        container, text = self._register()
        notifications.notify_warning("stream is offline")
        assert text.value == "stream is offline"
        assert container.visible is True
        container.update.assert_called()

    def test_transient_notify_also_shows_snackbar(self):
        """The chip is additive: the SnackBar must still fire so background
        errors stay visible when the phone's mobile controls (which hold the
        chip) are auto-hidden."""
        self._register()
        with mock.patch.object(notifications, "_show_snackbar") as snackbar:
            notifications.notify("added to Favorites")
        snackbar.assert_called_once()

    def test_persist_notify_also_shows_snackbar(self):
        """Persistent warnings must outlive the chip's auto-hide."""
        self._register()
        with mock.patch.object(notifications, "_show_snackbar") as snackbar:
            notifications.notify_error("offline", persist=True)
        snackbar.assert_called_once()

    def test_snackbar_fallback_when_no_chip_registered(self):
        notifications.unregister_fullscreen_toast()
        with mock.patch.object(notifications, "_show_snackbar") as snackbar:
            notifications.notify("no chip registered")
        snackbar.assert_called_once()

    def test_unregister_clears_registration(self):
        self._register()
        notifications.unregister_fullscreen_toast()
        assert notifications._fullscreen_toast["container"] is None
        assert notifications._fullscreen_toast["text"] is None
        assert notifications._fullscreen_toast["active"] is False

    def test_notify_after_unregister_does_not_crash(self):
        notifications.unregister_fullscreen_toast()
        notifications.notify("no chip registered")

    def test_hide_window_is_readable_on_phone(self):
        """6s > the mobile controls' 6s hover duration: a tap that re-mounts
        the controls right after the hover expiry still reveals the toast."""
        assert notifications._TOAST_HIDE_AFTER >= 6.0

    @pytest.mark.asyncio
    async def test_chip_auto_hides(self, monkeypatch):
        monkeypatch.setattr(notifications, "_TOAST_HIDE_AFTER", 0.05)
        container, _text = self._register()
        notifications.notify("fade away")
        await asyncio.sleep(0.15)
        assert container.visible is False
