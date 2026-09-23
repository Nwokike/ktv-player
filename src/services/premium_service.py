"""Premium (remove-ads) unlock via flet-billing / Google Play Billing.

Portable pattern — see the "Recipe: premium / remove-ads" section in the
flet-billing README. Core rules:

- Boot reads the local flag first (instant UI), then reconciles with the
  store (upgrade-only; a failed store check never downgrades the flag).
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
        self.billing = Billing(on_purchase_updated=self._on_purchases)
        page.services.append(self.billing)
        self.price: str | None = None

    async def restore(self) -> None:
        """Boot sequence: instant local flag, then reconcile with the store."""
        try:
            if await db_manager.get_setting("premium") == "true":
                state.is_premium = True
        except Exception:
            logger.warning("Could not read premium flag", exc_info=True)

        try:
            if not await self.billing.is_available():
                return
            result = await self.billing.query_products([PREMIUM_PRODUCT_ID])
            if result.products:
                self.price = result.products[0].price
            # Android-only fast path; iOS/desktop rely on restore_purchases
            # events below (query_past_purchases raises off-Android).
            try:
                owned = await self.billing.query_past_purchases()
                if any(
                    p.product_id == PREMIUM_PRODUCT_ID
                    and p.status is PurchaseStatus.PURCHASED
                    for p in owned.purchases
                ):
                    await self._activate()
            except Exception:
                logger.debug("query_past_purchases unavailable here", exc_info=True)
            await self.billing.restore_purchases()
        except Exception:
            logger.warning(
                "Premium store check failed; keeping local flag", exc_info=True
            )

    async def buy(self) -> bool:
        """Start the one-time premium purchase. Result arrives via the
        purchase-stream handler."""
        try:
            return await self.billing.buy_non_consumable(PREMIUM_PRODUCT_ID)
        except Exception:
            logger.exception("Premium purchase request failed")
            return False

    async def restore_purchases(self) -> None:
        """Manual restore (Settings button) — results arrive via events."""
        await self.billing.restore_purchases()

    async def _on_purchases(self, e) -> None:
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
