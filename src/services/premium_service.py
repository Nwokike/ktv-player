"""Premium (remove-ads) unlock via flet-billing / Google Play Billing.

Portable pattern — see the "Recipe: premium / remove-ads" section in the
flet-billing README. Core rules:

- Billing attaches on **mobile only**: ``in_app_purchase`` has no desktop
  platform, and a desktop invoke would stall for the full timeout on boot.
  Off-mobile everything here is an instant no-op.
- Boot reads the local flag first (instant UI), then reconciles with the
  store (upgrade-only; a failed store check never downgrades the flag).
- Buy re-queries the product first: the Play product may have been
  created after boot, and listing propagation lags. A product the store
  doesn't know yet is a friendly False, not an exception.
- Every ``purchased``/``restored`` transaction is acknowledged with
  ``complete_purchase()`` inside the event handler (3-day Play rule).
- Entitlements should still be verified server-side using
  ``verification_data.server_verification_data`` for anything valuable.
"""

import logging

from flet_billing import Billing, PurchaseStatus

from core.state import state
from database.manager import db_manager

logger = logging.getLogger(__name__)

PREMIUM_PRODUCT_ID = "premium_unlock"


class PremiumService:
    """Owns the Billing service and the persisted ``premium`` flag."""

    def __init__(self, page):
        self.page = page
        self.billing: Billing | None = None
        self.price: str | None = None
        if self._billing_supported():
            self.billing = Billing(on_purchase_updated=self._on_purchases)
            page.services.append(self.billing)

    def _billing_supported(self) -> bool:
        try:
            return bool(self.page.platform.is_mobile())
        except Exception:
            return False

    @property
    def available(self) -> bool:
        """True when a Billing service is attached (mobile builds)."""
        return self.billing is not None

    async def restore(self) -> None:
        """Boot sequence: instant local flag, then reconcile with the store."""
        try:
            if await db_manager.get_setting("premium") == "true":
                state.is_premium = True
        except Exception:
            logger.warning("Could not read premium flag", exc_info=True)

        if self.billing is None:
            return
        try:
            if not await self.billing.is_available():
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
            owned = await self.billing.query_past_purchases()
            if any(
                p.product_id == PREMIUM_PRODUCT_ID
                and p.status is PurchaseStatus.PURCHASED
                for p in owned.purchases
            ):
                await self._activate()
        except Exception:
            logger.debug("query_past_purchases unavailable here", exc_info=True)
        try:
            await self.billing.restore_purchases()
        except Exception:
            logger.debug("restore_purchases failed", exc_info=True)

    async def _refresh_product(self) -> bool:
        """Query the premium product.

        Returns False when this build/store doesn't know the product yet
        (not created in Play Console, or listing still propagating) — an
        expected state, logged at info level, not an error.
        """
        if self.billing is None:
            return False
        try:
            result = await self.billing.query_products([PREMIUM_PRODUCT_ID])
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
            await self.billing.restore_purchases()
        except Exception:
            logger.debug("restore_purchases failed", exc_info=True)

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
                logger.warning(
                    "Purchase error: %s",
                    p.error.message if p.error else "unknown",
                )
                try:
                    # Android: Play overlay e.g. for declined payment methods.
                    await self.billing.show_in_app_messages()
                except Exception:
                    logger.debug("show_in_app_messages unavailable", exc_info=True)

    async def _activate(self) -> None:
        if state.is_premium:
            return
        state.is_premium = True
        await db_manager.set_setting("premium", "true")
        logger.info("Premium activated — ads disabled")
