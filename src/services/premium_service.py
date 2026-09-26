"""Premium (remove-ads) unlock through the Kiri License Worker.

Single backend: **Kiri License** (license.kiri.ng) — Flutterwave checkout
and a signed entitlement token. It works on direct APK installs,
Windows and Linux with no Google permission at all.

Google Play Billing is not part of this build: the Play Console in use
has no Google Payments merchant profile, so there is nothing to sell
with and nothing testable. The Play AAB therefore ships free-only (see
core/channel.py), and this service goes inert on that channel — no
worker requests, no purchase UI, no cached entitlement can unlock it.

Core rules:

- The entitlement is a **signed token**, verified offline on every start
  (services.license_token) — never a bare local flag. A rejected or
  expired token drops premium.
- The recovery ID is stored immediately: it is the only way back in after
  the user clears app data.
- Every entitlement change is broadcast to listeners, so Settings
  re-renders the moment a purchase lands or a license lapses.
"""

import asyncio
import logging
import time
from collections.abc import Callable

from core.channel import CHANNEL
from core.state import state
from services.kiri_license import KiriLicenseService, LicenseUnavailable
from utils.notifications import notify

logger = logging.getLogger(__name__)

# Cadence, deliberately asymmetric:
# - checkout: seconds, because the user is holding the phone waiting for
#   the money to land. Flutterwave's hosted session is ~15 minutes.
# - steady state: hourly + on foreground resume + at launch. Entitlements
#   change at month boundaries, not second boundaries — a per-minute loop
#   would burn battery and drain the Worker's shared 20 req/60s budget for
#   nothing. The signed token's own `exp` enforces expiry offline anyway;
#   these checks exist to refresh renewals and catch revokes while running.
CHECKOUT_WATCH_INTERVAL = 5.0
CHECKOUT_WATCH_TIMEOUT = 15 * 60.0
RECONCILE_INTERVAL = 60 * 60.0
RESUME_DEBOUNCE = 60.0


class PremiumService:
    """Owns the Kiri license and derives the ``premium`` flag from it."""

    def __init__(self, page):
        self.page = page
        self.backend: str = "none"  # "kiri" | "none"
        self._listeners: list[Callable[[], None]] = []
        self.license = KiriLicenseService(on_change=self._recompute_premium)
        # Strong refs: asyncio only holds weak references to tasks, and a
        # bare create_task can be collected mid-flight (ad_service pattern).
        self._checkout_watch_task: asyncio.Task | None = None
        self._reconcile_task: asyncio.Task | None = None
        # Negative so the very first resume check is never debounced away.
        self._last_reconcile_at = time.monotonic() - RESUME_DEBOUNCE
        if CHANNEL == "play":
            # Free-only build: no purchase surface of any kind is wired up.
            logger.info("Play channel build — premium disabled, free tier with ads")
            return
        self.backend = "kiri"

    def _recompute_premium(self) -> None:
        """Mirror the license verdict into the app-wide premium flag."""
        unlocked = self.license.unlocked
        if state.is_premium != unlocked:
            logger.info("Premium state -> %s (kiri)", unlocked)
        state.is_premium = unlocked
        self._notify_listeners()

    def add_listener(self, callback: Callable[[], None]) -> None:
        """Observe entitlement changes (SettingsScreen re-renders)."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self) -> None:
        for callback in list(self._listeners):
            try:
                callback()
            except Exception:
                logger.debug("Premium listener failed", exc_info=True)

    @property
    def available(self) -> bool:
        """True when this build can offer a purchase at all."""
        return self.backend == "kiri"

    def _premium_disabled(self) -> bool:
        if CHANNEL == "play":
            logger.info("Purchase ignored: the Play build has no premium")
            return True
        return False

    async def load_local(self) -> None:
        """Verify the cached signed token — safe on the boot path.

        Offline by design: a paid app keeps premium with no network at
        all, and a token that no longer verifies (expired, tampered,
        revoked) drops it again.
        """
        if CHANNEL == "play":
            # Free-only build: a token left over from a direct install
            # must never unlock it.
            state.is_premium = False
            return
        try:
            await self.license.apply_cached_token()
        except Exception:
            logger.warning("Could not verify the cached license", exc_info=True)
        self._recompute_premium()

    async def reconcile(self) -> None:
        """Refresh the entitlement with the Worker.

        A network round-trip, so this runs *after* the first frame
        (AppController._post_render_startup), never before it. It runs
        even while unlocked: the Worker is authoritative when reachable,
        so a refunded or revoked license must land. Only a network failure
        keeps the local verdict.

        Uses the **token-issuing** path on purpose: `/status` never re-issues
        the signed token, so after a renewal the cached token's `exp` would
        lapse while the server still said `active` — a paying subscriber
        locked out until a manual Restore. `restore()` answers the same and
        re-arms the token in one round-trip (same rate bucket).
        """
        if CHANNEL == "play":
            return
        self._last_reconcile_at = time.monotonic()
        recovery_id = await self.license.recovery_id()
        if not recovery_id:
            # Nothing was ever purchased — nothing to reconcile.
            self._recompute_premium()
            return
        try:
            await self.license.restore(recovery_id)
        except LicenseUnavailable as ex:
            logger.info("Kiri license refresh: %s", ex)
        except Exception:
            logger.debug("Kiri license refresh failed", exc_info=True)
        finally:
            # Re-derive even on failure: a refusal or a rejected token has
            # already cleared the license, and state.is_premium must follow.
            self._recompute_premium()

    async def reconcile_if_due(self) -> None:
        """Debounced reconcile for foreground-resume and the hourly loop.

        RESUME/SHOW arrives in bursts (app switcher flickers, permission
        dialogs); without the debounce a burst could burn the Worker's
        shared 20 req/60s per-IP budget in one second.
        """
        if self._premium_disabled():
            return
        if time.monotonic() - self._last_reconcile_at < RESUME_DEBOUNCE:
            return
        await self.reconcile()

    # -- background watchers -------------------------------------------------

    def start_reconcile_loop(self) -> None:
        """Hourly entitlement check while the app runs (after boot reconcile)."""
        if self._premium_disabled():
            return
        self.stop_reconcile_loop()
        self._reconcile_task = self.page.run_task(self._reconcile_loop)
        logger.info(
            "Hourly license reconcile started (interval %.0fs)", RECONCILE_INTERVAL
        )

    def stop_reconcile_loop(self) -> None:
        task = self._reconcile_task
        self._reconcile_task = None
        if task is not None and not task.done():
            task.cancel()

    async def _reconcile_loop(self) -> None:
        while True:
            await asyncio.sleep(RECONCILE_INTERVAL)
            await self.reconcile_if_due()

    def start_checkout_watch(self, recovery_id: str) -> None:
        """Finish a hosted payment automatically: poll restore every few
        seconds until the server confirms, the window ends, or the app closes.

        Lives on the service (not the Settings screen) so navigating away,
        opening the player, or rebuilding the tab cannot orphan it.
        """
        if self._premium_disabled() or not recovery_id:
            return
        self.stop_checkout_watch()
        self._checkout_watch_task = self.page.run_task(
            self._checkout_watch_loop, recovery_id
        )
        logger.info(
            "Checkout watcher started (interval %.0fs)", CHECKOUT_WATCH_INTERVAL
        )

    def stop_checkout_watch(self) -> None:
        task = self._checkout_watch_task
        self._checkout_watch_task = None
        if task is not None and not task.done():
            task.cancel()

    async def _checkout_watch_loop(self, recovery_id: str) -> None:
        deadline = time.monotonic() + CHECKOUT_WATCH_TIMEOUT
        while time.monotonic() < deadline:
            await asyncio.sleep(CHECKOUT_WATCH_INTERVAL)
            try:
                status = await self.license.restore(recovery_id)
            except LicenseUnavailable as ex:
                # Pending (202), not verified yet (404/402), throttled (429)
                # or offline — the money is still moving; keep waiting.
                logger.info("Checkout watcher waiting: %s", ex)
                continue
            if status.status in ("active", "grace") and self.license.unlocked:
                # restore() already stored the token and flipped the flag
                # (license on_change -> _recompute_premium); listeners have
                # rebuilt every screen — this is just the human confirmation.
                # `unlocked` (not just the status text) demands a verified
                # token, so a signing misconfiguration can never toast a lie.
                logger.info(
                    "Checkout watcher unlocked product=%s status=%s",
                    status.product,
                    status.status,
                )
                notify("Premium unlocked — ads removed")
                return
        logger.info("Checkout watcher timed out — Restore purchases remains available")

    def shutdown(self) -> None:
        """Cancel every background task (app close)."""
        self.stop_checkout_watch()
        self.stop_reconcile_loop()

    # -- Kiri License surface ------------------------------------------------

    async def kiri_catalog(self):
        """Products offered by the license Worker, or [] when offline."""
        if self._premium_disabled():
            return []
        try:
            return await self.license.fetch_catalog()
        except LicenseUnavailable as ex:
            logger.info("License catalog unavailable: %s", ex)
            return []
        except Exception:
            logger.debug("License catalog failed", exc_info=True)
            return []

    async def kiri_checkout(self, product_id: str, email: str):
        """Create a hosted payment, save the recovery ID, start auto-finish."""
        if self._premium_disabled():
            raise LicenseUnavailable("Premium is not available in this build")
        checkout = await self.license.checkout(product_id, email)
        self._notify_listeners()
        # The browser takes over from here; this watcher is what makes the
        # app unlock itself when the user comes back with a paid checkout.
        self.start_checkout_watch(checkout.recovery_id)
        return checkout

    async def kiri_restore(self, recovery_id: str):
        """Redeem a recovery ID; raises LicenseUnavailable with a reason."""
        if self._premium_disabled():
            raise LicenseUnavailable("Premium is not available in this build")
        status = await self.license.restore(recovery_id)
        self._recompute_premium()
        return status

    async def kiri_check_status(self):
        """Re-check the saved entitlement, keeping the local token offline."""
        if self._premium_disabled():
            return None
        status = await self.license.refresh()
        self._recompute_premium()
        return status
