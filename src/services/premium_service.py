"""Premium (remove-ads) unlock via flet-billing / Google Play Billing.

Portable pattern — see the "Recipe: premium / remove-ads" section in the
flet-billing README. Core rules:

- Billing attaches on **Android phones and Android TV**: ``in_app_purchase``
  has no desktop or web platform, and an invoke there would stall for the
  full timeout on boot. Everywhere else this service is an instant no-op.
- Boot reads the local flag first (instant UI, before the first frame), then
  reconciles with the store *after* the first render (upgrade-only; a failed
  store check never downgrades the flag).
- Buy re-queries the product first: the Play product may have been
  created after boot, and listing propagation lags. A product the store
  doesn't know yet is a friendly False, not an exception.
- Every ``purchased``/``restored`` transaction is acknowledged with
  ``complete_purchase()`` inside the event handler (3-day Play rule).
- Entitlements should still be verified server-side using
  ``verification_data.server_verification_data`` for anything valuable.
"""

import logging
from collections.abc import Callable

import flet as ft
from flet_billing import Billing, PurchaseStatus

from core.state import state
from database.manager import db_manager

logger = logging.getLogger(__name__)

PREMIUM_PRODUCT_ID = "premium_unlock"

# Play round-trips are given a shorter leash than flet-billing's 10s default:
# these run on app resume and behind a settings button, where a stalled
# network should surface as a message rather than a spinner that never ends.
STORE_TIMEOUT = 6.0


class PremiumService:
    """Owns the Billing service and the persisted ``premium`` flag."""

    def __init__(self, page):
        self.page = page
        self.billing: Billing | None = None
        self.price: str | None = None
        self._listeners: list[Callable[[], None]] = []
        if self._billing_supported():
            self.billing = Billing(on_purchase_updated=self._on_purchases)
            # Service auto-registers against context.page (flet
            # service.py:__post_init__); appending again would register the
            # same instance twice.
            if self.billing not in page.services:
                page.services.append(self.billing)

    def _billing_supported(self) -> bool:
        """Android phones and Android TV both have a Play Store; desktop and
        web have no in-app-purchase platform at all, where every invoke
        would stall for the full timeout."""
        try:
            platform = self.page.platform
            return bool(platform.is_mobile() or platform == ft.PagePlatform.ANDROID_TV)
        except Exception:
            return False

    def add_listener(self, callback: Callable[[], None]) -> None:
        """Observe entitlement/price changes (SettingsScreen re-renders)."""
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
        """True when a Billing service is attached (mobile/TV builds)."""
        return self.billing is not None

    async def load_local(self) -> None:
        """Read the persisted entitlement — one DB row, safe on the boot path."""
        try:
            if await db_manager.get_setting("premium") == "true":
                state.is_premium = True
        except Exception:
            logger.warning("Could not read premium flag", exc_info=True)

    async def reconcile(self) -> None:
        """Reconcile ownership with the store.

        Every call here is a network round-trip, so this runs *after* the
        first frame (AppController._post_render_startup), never before it.
        A failed store check never downgrades the local flag.
        """
        if self.billing is None:
            return
        try:
            if not await self.billing.is_available(timeout=STORE_TIMEOUT):
                return
        except TimeoutError:
            logger.info(
                "Billing store check unavailable (timeout) — keeping local flag"
            )
            return
        except Exception:
            logger.warning(
                "Billing store check failed; keeping local flag", exc_info=True
            )
            return

        await self._refresh_product()
        try:
            # Android-only fast path; iOS relies on restore_purchases events
            # below (query_past_purchases raises off-Android).
            owned = await self.billing.query_past_purchases(timeout=STORE_TIMEOUT)
            if any(
                p.product_id == PREMIUM_PRODUCT_ID
                and p.status is PurchaseStatus.PURCHASED
                for p in owned.purchases
            ):
                await self._activate()
        except Exception:
            logger.debug("query_past_purchases unavailable here", exc_info=True)
        try:
            await self.billing.restore_purchases(timeout=STORE_TIMEOUT)
        except Exception:
            logger.debug("restore_purchases failed", exc_info=True)

    async def restore(self) -> None:
        """Full boot sequence: instant local flag, then store reconciliation."""
        await self.load_local()
        await self.reconcile()

    async def _refresh_product(self) -> bool:
        """Query the premium product.

        Returns False when this build/store doesn't know the product yet
        (not created in Play Console, or listing still propagating) — an
        expected state, logged at info level, not an error.
        """
        if self.billing is None:
            return False
        try:
            result = await self.billing.query_products(
                [PREMIUM_PRODUCT_ID], timeout=STORE_TIMEOUT
            )
            if result.error:
                logger.info("Premium product query error: %s", result.error.message)
                return False
            product = next(
                (p for p in result.products if p.id == PREMIUM_PRODUCT_ID), None
            )
        except Exception:
            logger.warning("Premium product query failed", exc_info=True)
            return False
        if product is None:
            logger.info(
                "Premium product '%s' is not available in this store yet",
                PREMIUM_PRODUCT_ID,
            )
            return False
        self.price = product.price
        self._notify_listeners()
        return True

    async def buy(self) -> bool:
        """Start the one-time premium purchase. Result arrives via the
        purchase-stream handler. False when the store doesn't offer the
        product (or the request could not start)."""
        if state.is_premium:
            return True
        if self.billing is None:
            logger.info("Premium purchase requested on an unsupported platform")
            return False
        if not await self._refresh_product():
            return False
        try:
            return await self.billing.buy_non_consumable(PREMIUM_PRODUCT_ID)
        except Exception:
            logger.exception("Premium purchase request failed")
            return False

    async def restore_purchases(self) -> None:
        """Manual restore (Settings button) — results arrive via events."""
        if self.billing is None:
            return
        try:
            await self.billing.restore_purchases(timeout=STORE_TIMEOUT)
        except Exception:
            logger.debug("restore_purchases failed", exc_info=True)

    def _is_android(self) -> bool:
        try:
            return self.page.platform in (
                ft.PagePlatform.ANDROID,
                ft.PagePlatform.ANDROID_TV,
            )
        except Exception:
            return False

    async def _on_purchases(self, e) -> None:
        if self.billing is None:
            return
        for p in e.purchases:
            if (
                p.status in (PurchaseStatus.PURCHASED, PurchaseStatus.RESTORED)
                and p.product_id == PREMIUM_PRODUCT_ID
            ):
                if p.pending_complete_purchase and p.purchase_id:
                    try:
                        await self.billing.complete_purchase(p.purchase_id)
                    except Exception:
                        logger.exception(
                            "complete_purchase failed for %s", p.purchase_id
                        )
                await self._activate()
            elif p.status is PurchaseStatus.ERROR:
                code = ((p.error.code if p.error else "") or "").lower()
                logger.warning(
                    "Purchase error: %s",
                    p.error.message if p.error else "unknown",
                )
                # The Play in-app-message overlay is only useful for a
                # declined payment — showing it for network/store errors
                # pops an unrelated dialog at the user.
                if "declin" in code and self._is_android():
                    try:
                        await self.billing.show_in_app_messages()
                    except Exception:
                        logger.debug("show_in_app_messages unavailable", exc_info=True)

    async def _activate(self) -> None:
        if state.is_premium:
            return
        state.is_premium = True
        self._notify_listeners()
        try:
            await db_manager.set_setting("premium", "true")
        except Exception:
            # The entitlement is live in RAM but won't survive a restart;
            # the next reconcile re-activates it from the store.
            logger.warning("Could not persist the premium flag", exc_info=True)
        logger.info("Premium activated — ads disabled")
