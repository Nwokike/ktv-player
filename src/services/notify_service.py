"""System notifications, via flet-notifications.

Everything user-visible that happens inside the player is invisible in
fullscreen: the app's own toast sits in the Flet control tree, and on the
Android fullscreen route (pushed above the whole page) there is nothing to
see. A system notification is the only feedback that survives that, and it
works on every platform the package supports (Android, iOS, macOS, Windows,
Linux, Web).

Two channels, because a channel's sound and vibration are fixed when it is
created and cannot be changed afterwards:

- ``ktv_feedback`` — silent. Screenshot saved, favourite toggled, scan
  finished. Things that confirm an action the user just took; a second of
  noise per photo would be unbearable.
- ``ktv_channel`` — default importance. A channel that was dead is back
  online, or a new version is available. Worth pulling the shade down for.

Nothing here is allowed to raise. A notification is a nice-to-have on top of
the action: if the backend is unavailable the action still happened, and the
caller must not have to care.
"""

import contextlib
import logging

logger = logging.getLogger(__name__)

try:  # pragma: no cover - the dependency is pinned in pyproject
    from flet_notifications import (
        Importance,
        LocalNotifications,
        NotificationChannel,
    )

    _HAS_NOTIFICATIONS = True
except ImportError:  # pragma: no cover
    _HAS_NOTIFICATIONS = False

_CHANNEL_FEEDBACK = "ktv_feedback"
_CHANNEL_ALERT = "ktv_channel"

# Stable notification ids. Re-showing the same id updates the existing
# notification in place rather than stacking a new one, which is what keeps
# a scan from leaving twenty bars behind.
_ID_FEEDBACK = 4100
_ID_CHANNEL_ONLINE = 4101
_ID_SCAN = 4102
_ID_UPDATE = 4103


class NotifyService:
    """Owns the one LocalNotifications instance and its channels.

    Follows the same shape as Sherlock's ScanNotifier, which is known to
    work in production: build the service lazily, latch ``_started`` only
    after a successful build so one transient failure does not disable
    notifications for the whole session, and re-check permission before the
    first post rather than latching it at startup (a user who turns
    notifications on later in Android settings gets them on the next action).
    """

    def __init__(self) -> None:
        self._service = None
        self._started = False
        self._channels_made = False
        self._ready = False

    # --- lifecycle ---

    def attach(self, page) -> None:
        """Remember the page used to schedule work on the UI loop."""
        self._page = page
        self._tap_handler = None

    def set_tap_handler(self, handler) -> None:
        """Install the handler run when any notification is tapped.

        The service is built lazily, so the handler is stashed here rather
        than assigned straight onto the LocalNotifications instance (which may
        not exist yet), and applied when it does.
        """
        self._tap_handler = handler
        if self._service is not None:
            with contextlib.suppress(Exception):
                self._service.on_tap = self._dispatch_tap

    def _dispatch_tap(self, event):
        handler = self._tap_handler
        if handler is None:
            return
        try:
            handler(event)
        except Exception:
            logger.debug("Notification tap handler failed", exc_info=True)

    async def ensure_ready(self) -> bool:
        """Build the service (once) and make sure the OS will deliver posts.

        Safe to call before every post: it is a no-op once started, and it
        re-checks permission so a user who enabled notifications after the
        app launched gets them without a restart.
        """
        if not _HAS_NOTIFICATIONS:
            return False
        try:
            if not self._started:
                await self._construct()
            if self._service is None:
                return False
            if self._ready:
                return True
            if await self._service.are_notifications_enabled():
                self._ready = True
                return True
            self._ready = bool(await self._service.request_permissions())
            return self._ready
        except Exception as exc:
            logger.debug("Notifications not ready: %s", exc)
            return False

    async def _construct(self) -> None:
        if self._started:
            return
        try:
            self._service = LocalNotifications()
            self._started = True
            if self._tap_handler is not None:
                with contextlib.suppress(Exception):
                    self._service.on_tap = self._dispatch_tap
            await self._ensure_channels()
        except Exception as exc:
            # A dead notification backend must never break the action that
            # wanted it.
            logger.warning("Notification backend unavailable: %s", exc)
            self._service = None

    async def _ensure_channels(self) -> None:
        if self._channels_made or self._service is None:
            return
        try:
            await self._service.create_notification_channel(
                NotificationChannel(
                    id=_CHANNEL_FEEDBACK,
                    name="KTV actions",
                    description="Confirms a screenshot, favourite or finished scan",
                    importance=Importance.LOW,
                    play_sound=False,
                    enable_vibration=False,
                    show_badge=False,
                )
            )
            await self._service.create_notification_channel(
                NotificationChannel(
                    id=_CHANNEL_ALERT,
                    name="Channel and update alerts",
                    description="A channel came back online, or an update is ready",
                    importance=Importance.DEFAULT,
                    show_badge=True,
                )
            )
            self._channels_made = True
        except Exception as exc:
            logger.warning("Notification channel setup failed: %s", exc)

    def is_usable(self) -> bool:
        """Synchronous probe, safe to consult from render or event code."""
        return self._service is not None and self._ready

    # --- posting ---

    async def feedback(self, title: str, body: str = "") -> bool:
        """Confirm something the user just did (silent channel)."""
        return await self._post(_ID_FEEDBACK, _CHANNEL_FEEDBACK, title, body)

    async def alert(self, title: str, body: str = "", payload: str = "") -> bool:
        """Something worth interrupting for (channel online, update)."""
        return await self._post(
            _ID_CHANNEL_ONLINE, _CHANNEL_ALERT, title, body, payload
        )

    async def progress(self, title: str, body: str, done: int, total: int) -> bool:
        """Update the one scan notification in place."""
        return await self._post(
            _ID_SCAN,
            _CHANNEL_FEEDBACK,
            title,
            body,
            show_progress=True,
            max_progress=total,
            progress=done,
        )

    async def _post(self, nid, channel, title, body, payload="", **kwargs) -> bool:
        if not await self.ensure_ready():
            return False
        try:
            await self._service.show(
                id=nid,
                title=title,
                body=body,
                payload=payload,
                channel_id=channel,
                **kwargs,
            )
            return True
        except Exception as exc:
            # show() raises NotificationError with a stable code; log it and
            # carry on, the action already happened.
            logger.debug(
                "Notification post failed (%s): %s", getattr(exc, "code", "?"), exc
            )
            return False

    def clear(self, *ids: int) -> None:
        """Drop posted notifications (used when the action is undone)."""
        if self._service is None:
            return
        page = getattr(self, "_page", None)
        if page is None:
            return
        for nid in ids:
            try:
                page.run_task(self._service.cancel, nid)
            except Exception:
                logger.debug("Notification cancel failed for id=%s", nid)


notify_service = NotifyService()
