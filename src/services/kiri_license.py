"""Kiri License client — external checkout for everything Play cannot bill.

Google Play only sells to Play-installed builds (or linked license testers),
so a GitHub-downloaded APK, the Windows build and the Linux build can never
complete a purchase through Play Billing. This client covers exactly those
surfaces, using the same Worker that backs every Kiri app:

    GET  /catalog   -> public products, prices, currency
    POST /checkout  -> Flutterwave hosted page + a recovery ID
    POST /restore   -> entitlement status and a signed offline token
    POST /status    -> status refresh without issuing a token

The Worker is authoritative; the token it returns is a signed cache that
keeps premium working offline (see :mod:`services.license_token`). Nothing
here unlocks premium by itself — a verified token or a live server response
must say so first.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from core.constants import (
    KIRI_LICENSE_APP_ID,
    KIRI_LICENSE_BASE_URL,
    KIRI_LICENSE_PUBLIC_KEY,
    KIRI_LICENSE_TIMEOUT,
)
from database.manager import db_manager
from services.http_client import get_http_client
from services.license_token import LicenseClaims, TokenRejected, verify_token

logger = logging.getLogger(__name__)

# Explicit 4-tuple from the scalar constant: pool acquisition stays tight
# (scalar 15 widened pool to 15s). No behavior change to refusal codes or
# retry — Phase 5 owns licensing semantics.
_LICENSE_TIMEOUT = httpx.Timeout(
    connect=5.0, read=KIRI_LICENSE_TIMEOUT, write=10.0, pool=3.0
)

SETTING_RECOVERY_ID = "kiri_recovery_id"
SETTING_TOKEN = "kiri_token"
SETTING_PRODUCT = "kiri_product"


class LicenseUnavailable(Exception):
    """The license service could not be reached or refused the request.

    `status_code` is the HTTP status when one exists (None for transport /
    parse failures); `is_refusal` is True only when the server answered that
    the entitlement itself is invalid (402/403/404). Callers branch on it:
    refusal aborts retry loops fast, transients back off and retry.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        is_refusal: bool = False,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.is_refusal = is_refusal


#: Refusals that abort the checkout watcher fast: payment invalid / app not
#: entitled will never turn active. 404 is a refusal for RECONCILE (a standing
#: license deleted server-side is gone) but NOT for the watcher (post-payment
#: the license may simply not exist yet — webhook lag). The watcher checks
#: membership here explicitly instead of reusing status_refusal().
WATCHER_ABORT_CODES = frozenset({402, 403})


def status_refusal(code: int) -> bool:
    """HTTP codes meaning "this entitlement is not valid" — not transport.

    402 payment not valid, 403 app not entitled, 404 license not found.
    400 is deliberately EXCLUDED: a malformed request is our bug, not proof
    the license died — revoking on it once de-premiumed paying users on an
    app bug. 429 is excluded too: a throttled check must never revoke.
    """
    return code in (402, 403, 404)


@dataclass(frozen=True)
class LicenseProduct:
    id: str
    amount: float
    currency: str
    kind: str
    description: str

    @property
    def price_label(self) -> str:
        symbol = {"USD": "$", "EUR": "€", "NGN": "₦"}.get(self.currency.upper(), "")
        amount = f"{self.amount:,.2f}".rstrip("0").rstrip(".")
        return f"{symbol}{amount} {self.currency.upper()}".strip()


@dataclass(frozen=True)
class Checkout:
    recovery_id: str
    checkout_url: str
    product: str
    amount: float
    currency: str


@dataclass(frozen=True)
class LicenseStatus:
    status: str
    product: str
    recovery_id: str
    token: str | None = None
    claims: LicenseClaims | None = None

    @property
    def unlocks(self) -> bool:
        """Display-only status text check. NEVER gate entitlements on this
        alone: a status-only reply carries no token, and status "active" with
        claims=None unlocks nothing. Use effective_unlocks(claims)."""
        return self.status in ("active", "grace")

    def effective_unlocks(self, claims: LicenseClaims | None) -> bool:
        """The only predicate allowed to grant or drop an unlock: verified
        status text AND a verified token. Shared by _apply and callers so a
        future status-alone check can't fool anyone."""
        return self.status in ("active", "grace") and claims is not None


class KiriLicenseService:
    """Talks to the Kiri License Worker and caches the signed entitlement."""

    def __init__(
        self,
        app_id: str = KIRI_LICENSE_APP_ID,
        public_key: str = KIRI_LICENSE_PUBLIC_KEY,
        on_change: Callable[[], None] | None = None,
    ):
        self.app_id = app_id
        # Injected rather than read from the constant at every call so a key
        # rotation (and the test fixtures, which are signed with their own
        # throwaway pair) is a constructor argument, not a monkeypatch.
        self.public_key = public_key
        # This service owns its own entitlement only: it reports the verdict
        # and lets PremiumService mirror it into the app-wide flag.
        self.on_change = on_change
        self.products: list[LicenseProduct] = []
        self.claims: LicenseClaims | None = None
        self._unlocked = False

    # -- local state ---------------------------------------------------------

    @property
    def unlocked(self) -> bool:
        return self._unlocked

    async def recovery_id(self) -> str:
        return await db_manager.get_setting(SETTING_RECOVERY_ID, "") or ""

    async def cached_product(self) -> str:
        return await db_manager.get_setting(SETTING_PRODUCT, "") or ""

    async def _store(
        self,
        *,
        recovery_id: str | None = None,
        token: str | None = None,
        product: str | None = None,
    ) -> None:
        if recovery_id is not None:
            await db_manager.set_setting(SETTING_RECOVERY_ID, recovery_id)
        if token is not None:
            await db_manager.set_setting(SETTING_TOKEN, token)
        if product is not None:
            await db_manager.set_setting(SETTING_PRODUCT, product)

    async def _revoke(self, reason: str) -> None:
        """Drop the unlock in memory AND on disk together.

        Every revoke path funnels here: clearing memory but leaving
        SETTING_TOKEN meant the next boot re-verified the bad token and
        re-unlocked (revoked stayed revoked for exactly one session).
        """
        self._unlocked = False
        self.claims = None
        await self._store(token="")
        logger.info("Kiri license revoked (%s); cached token cleared", reason)
        self._notify_change()

    async def _apply(self, status: str, claims: LicenseClaims | None) -> None:
        """Record a verified entitlement and let the app re-evaluate.

        Deliberately does NOT set `state.is_premium` itself: the caller
        re-derives it from a single source of truth, so an entitlement can
        only be granted or dropped in one place.
        """
        self._unlocked = LicenseStatus(
            status=status, product="", recovery_id=""
        ).effective_unlocks(claims)
        logger.info(
            "Kiri license status=%s product=%s unlocked=%s",
            status,
            claims.product if claims else "-",
            self._unlocked,
        )
        self._notify_change()

    # -- offline -------------------------------------------------------------

    async def apply_cached_token(self) -> bool:
        """Verify the stored token so premium survives being offline.

        Returns whether the app is unlocked. A rejected token is cleared
        rather than left to fail on every launch.
        """
        token = await db_manager.get_setting(SETTING_TOKEN, "")
        if not token:
            self._unlocked = False
            # Without the token there is nothing left to verify, so the old
            # claims must not be reused by a later status reply.
            self.claims = None
            self._notify_change()
            return False
        try:
            claims = verify_token(token, self.public_key, self.app_id)
        except TokenRejected as ex:
            # Rejected here too — not just in memory: a bad token left on
            # disk fails every future boot the same way.
            logger.info("Cached Kiri license rejected (%s)", ex.reason)
            await self._revoke(f"cached token rejected: {ex.reason}")
            return False
        self.claims = claims
        await self._apply(claims.status, claims)
        return self._unlocked

    # -- server --------------------------------------------------------------

    async def fetch_catalog(self, force: bool = False) -> list[LicenseProduct]:
        if self.products and not force:
            return self.products
        try:
            response = await get_http_client().get(
                f"{KIRI_LICENSE_BASE_URL.rstrip('/')}/catalog",
                timeout=_LICENSE_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as ex:
            raise LicenseUnavailable(
                f"Could not reach the license service: {ex}"
            ) from ex
        if not isinstance(payload, dict):
            raise LicenseUnavailable("The license service returned an invalid response")
        products = []
        for item in payload.get("products", []):
            if not isinstance(item, dict) or not item.get("id"):
                continue
            try:
                amount = float(item.get("amount") or 0)
                currency = str(item.get("currency") or "USD")
            except (TypeError, ValueError) as ex:
                raise LicenseUnavailable(
                    f"Invalid product pricing for {item.get('id')}: {ex}"
                ) from ex
            products.append(
                LicenseProduct(
                    id=str(item.get("id", "")),
                    amount=amount,
                    currency=currency,
                    kind=str(item.get("kind") or "one_time"),
                    description=str(item.get("description") or ""),
                )
            )
        self.products = products
        return self.products

    async def checkout(self, product_id: str, email: str) -> Checkout:
        """Start a hosted payment and return where to send the user."""
        product_id = (product_id or "").strip()
        email = (email or "").strip().lower()
        if not product_id:
            raise LicenseUnavailable("Choose a product first")
        if not email or "@" not in email:
            raise LicenseUnavailable("Enter a valid email for your receipt")
        try:
            response = await get_http_client().post(
                f"{KIRI_LICENSE_BASE_URL.rstrip('/')}/checkout",
                json={"app_id": self.app_id, "product_id": product_id, "email": email},
                timeout=_LICENSE_TIMEOUT,
            )
        except Exception as ex:
            raise LicenseUnavailable(
                f"Could not reach the license service: {ex}"
            ) from ex
        if response.status_code >= 400:
            raise LicenseUnavailable(
                self._error_message(response, "Checkout failed"),
                status_code=response.status_code,
                is_refusal=status_refusal(response.status_code),
            )
        try:
            payload = response.json()
        except Exception as ex:
            raise LicenseUnavailable(
                "The license service returned invalid JSON"
            ) from ex
        if not isinstance(payload, dict):
            raise LicenseUnavailable("The license service returned an invalid response")
        try:
            amount = float(payload.get("amount") or 0)
            currency = str(payload.get("currency") or "USD")
        except (TypeError, ValueError) as ex:
            raise LicenseUnavailable(f"Invalid order pricing: {ex}") from ex
        checkout = Checkout(
            recovery_id=str(payload.get("recovery_id") or ""),
            checkout_url=str(payload.get("checkout_url") or ""),
            product=str(payload.get("product") or product_id),
            amount=amount,
            currency=currency,
        )
        if not checkout.checkout_url or not checkout.recovery_id:
            raise LicenseUnavailable("The license service returned an incomplete order")
        # Persist the recovery ID immediately: it is the only way back in
        # after the user clears app data.
        await self._store(recovery_id=checkout.recovery_id, product=checkout.product)
        return checkout

    async def restore(self, recovery_id: str) -> LicenseStatus:
        """Redeem a recovery ID and cache the signed entitlement."""
        return await self._query("/restore", recovery_id, issue_token=True)

    async def refresh(self) -> LicenseStatus | None:
        """Re-check the stored entitlement (no token issued)."""
        recovery_id = await self.recovery_id()
        if not recovery_id:
            return None
        return await self._query("/status", recovery_id, issue_token=False)

    def _notify_change(self) -> None:
        """Report a verdict change so the app-wide flag cannot go stale."""
        if self.on_change is not None:
            self.on_change()

    async def _post(self, path: str, body: dict):
        """Single POST attempt with typed errors. Refusals carry is_refusal;
        everything else is transient (retryable, never revokes)."""
        try:
            response = await get_http_client().post(
                f"{KIRI_LICENSE_BASE_URL.rstrip('/')}{path}",
                json=body,
                timeout=_LICENSE_TIMEOUT,
            )
        except Exception as ex:
            raise LicenseUnavailable(
                f"Could not reach the license service: {ex}"
            ) from ex
        if response.status_code >= 400:
            raise LicenseUnavailable(
                self._error_message(response, "Restore failed"),
                status_code=response.status_code,
                is_refusal=status_refusal(response.status_code),
            )
        try:
            payload = response.json()
        except Exception as ex:
            raise LicenseUnavailable(
                "The license service returned invalid JSON"
            ) from ex
        if not isinstance(payload, dict):
            raise LicenseUnavailable("The license service returned an invalid response")
        return payload

    async def _query(
        self, path: str, recovery_id: str, *, issue_token: bool
    ) -> LicenseStatus:
        recovery_id = (recovery_id or "").strip()
        if not recovery_id:
            raise LicenseUnavailable("Enter the recovery ID from your purchase email")
        # One immediate retry on TRANSIENT failure (Worker glitch, blip):
        # a single 404/timeout must not drop a valid cached unlock. Refusals
        # (402/403/404 entitlement answers) never retry — the server spoke.
        # The consecutive-failure gate lives in premium_service: 2 straight
        # transient failures in a row revoke; any success resets it.
        try:
            payload = await self._post(
                path, {"recovery_id": recovery_id, "app_id": self.app_id}
            )
        except LicenseUnavailable as ex:
            if ex.is_refusal:
                # The server answered that the entitlement is invalid: drop
                # the unlock in memory AND on disk before surfacing. A memory-
                # only wipe would re-unlock next boot from the cached token.
                await self._revoke(f"server refusal HTTP {ex.status_code}")
                raise
            logger.info("License request transient failure, retrying once: %s", ex)
            payload = await self._post(
                path, {"recovery_id": recovery_id, "app_id": self.app_id}
            )
        status = str(payload.get("status") or "unknown")
        token = payload.get("token") if issue_token else None
        if token is not None and not isinstance(token, str):
            raise LicenseUnavailable("The license service returned a malformed token")
        claims: LicenseClaims | None = None
        if token:
            try:
                claims = verify_token(token, self.public_key, self.app_id)
            except TokenRejected as ex:
                # A token we cannot verify is a token we do not honour, even
                # if the server said the license is active — and one that was
                # previously trusted must be dropped from disk too, not kept
                # on the shelf to re-unlock next boot.
                logger.warning("Kiri license token rejected: %s", ex.reason)
                await self._revoke(f"unverifiable token: {ex.reason}")
                raise LicenseUnavailable(
                    "The license service returned a token this app could not verify"
                ) from ex
            if status in ("active", "grace"):
                await self._store(
                    recovery_id=str(payload.get("recovery_id") or recovery_id),
                    token=token,
                    product=str(payload.get("product") or ""),
                )
            else:
                # A valid token for a revoked/expired license must not be
                # cached: next launch would verify it and re-unlock.
                logger.info("Not caching token for status=%s", status)
                await self._store(
                    recovery_id=str(payload.get("recovery_id") or recovery_id),
                    token="",
                    product=str(payload.get("product") or ""),
                )
        else:
            await self._store(
                recovery_id=str(payload.get("recovery_id") or recovery_id),
                product=str(payload.get("product") or ""),
            )
        # A fresh verified token replaces the cache; a status-only reply
        # (which carries no token by design) reuses the one we already
        # verified — the assignment must come after that read, or every
        # refresh wipes the cache with None and unlocks nothing.
        if claims is not None:
            self.claims = claims
        effective = claims if claims is not None else self.claims
        if status not in ("active", "grace"):
            # Revoked/expired WITHOUT a token branch above: drop the disk
            # token too (the token-present branch already cleared it). A stale
            # cached token would otherwise re-unlock next boot.
            await self._revoke(f"server status={status}")
            effective = None
        await self._apply(status, effective)
        return LicenseStatus(
            status=status,
            product=str(payload.get("product") or ""),
            recovery_id=str(payload.get("recovery_id") or recovery_id),
            token=token,
            claims=claims,
        )

    @staticmethod
    def _error_message(response, fallback: str) -> str:
        try:
            body = response.json()
            if isinstance(body, dict) and body.get("message"):
                return str(body["message"])
            if isinstance(body, dict) and body.get("error"):
                return str(body["error"])
        except Exception:
            pass
        return f"{fallback} (HTTP {response.status_code})"
