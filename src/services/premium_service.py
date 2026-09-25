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

import logging
from collections.abc import Callable

from core.channel import CHANNEL
from core.state import state
from services.kiri_license import KiriLicenseService, LicenseUnavailable

logger = logging.getLogger(__name__)


class PremiumService:
    """Owns the Kiri license and the persisted ``premium`` flag."""

    def __init__(self, page):
        self.page = page
        self.backend: str = "none"  # "kiri" | "none"
        self._listeners: list[Callable[[], None]] = []
        self.license = KiriLicenseService(on_change=self._recompute_premium)
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
        """
        if CHANNEL == "play":
            return
        try:
            await self.license.refresh()
        except LicenseUnavailable as ex:
            logger.info("Kiri license refresh skipped: %s", ex)
        except Exception:
            logger.debug("Kiri license refresh failed", exc_info=True)

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
        """Create a hosted payment and save the recovery ID."""
        if self._premium_disabled():
            raise LicenseUnavailable("Premium is not available in this build")
        checkout = await self.license.checkout(product_id, email)
        self._notify_listeners()
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
