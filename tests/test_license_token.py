"""The offline entitlement verifier, tested against real Worker signatures.

The fixtures in license_fixtures.py are signed by the license Worker's own
token.js (WebCrypto ECDSA P-256), so these tests fail if the Python
implementation and the server ever disagree about the token format.
"""

import base64
import time

import pytest

from services.license_token import TokenRejected, verify_token
from tests.license_fixtures import PUBLIC_KEY, TOKENS

APP = "ng.kiri.ktvplayer"
NOW = 1758600000  # the iat carried by every fixture


def test_lifetime_token_verifies():
    claims = verify_token(TOKENS["LIFETIME"], PUBLIC_KEY, APP, now=NOW)
    assert claims.status == "active"
    assert claims.product == "lifetime"
    assert claims.scope == "universal"
    assert claims.is_lifetime is True


def test_recurring_token_reports_its_expiry():
    claims = verify_token(TOKENS["YEARLY_ACTIVE"], PUBLIC_KEY, APP, now=NOW)
    assert claims.product == "yearly"
    assert claims.mode == "recurring"
    assert claims.expires_at == 1790000000
    assert claims.is_lifetime is False


def test_grace_period_still_unlocks():
    claims = verify_token(TOKENS["GRACE"], PUBLIC_KEY, APP, now=NOW)
    assert claims.status == "grace"


@pytest.mark.parametrize(
    ("fixture", "reason"),
    [
        ("EXPIRED", "expired"),
        ("REVOKED", "revoked"),
        ("WRONG_APP", "wrong_app"),
        ("BAD_ISSUER", "bad_issuer"),
        ("UNSUPPORTED_VERSION", "unsupported_version"),
    ],
)
def test_rejected_tokens_name_their_reason(fixture, reason):
    with pytest.raises(TokenRejected) as caught:
        verify_token(TOKENS[fixture], PUBLIC_KEY, APP, now=NOW)
    assert caught.value.reason == reason


def test_expiry_is_evaluated_against_the_current_time():
    """The same token unlocks before exp and stops at exp."""
    with pytest.raises(TokenRejected) as caught:
        verify_token(TOKENS["EXPIRING_SOON"], PUBLIC_KEY, APP, now=1758600060)
    assert caught.value.reason == "expired"

    claims = verify_token(TOKENS["EXPIRING_SOON"], PUBLIC_KEY, APP, now=1758600059)
    assert claims.status == "active"


def test_tampered_payload_is_rejected():
    """Editing the claims must invalidate the signature."""
    header, payload, signature = TOKENS["LIFETIME"].split(".")
    claims = base64.urlsafe_b64decode(payload + "==")
    forged = claims.replace(b'"app":"ng.kiri.ktvplayer"', b'"app":"com.evil.app"')
    assert forged != claims
    forged_b64 = base64.urlsafe_b64encode(forged).decode().rstrip("=")
    with pytest.raises(TokenRejected) as caught:
        verify_token(f"{header}.{forged_b64}.{signature}", PUBLIC_KEY, APP, now=NOW)
    assert caught.value.reason == "bad_signature"


def test_token_from_another_key_is_rejected():
    with pytest.raises(TokenRejected) as caught:
        verify_token(
            TOKENS["LIFETIME"],
            # A different (valid) P-256 public key must not verify it.
            "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEuK1vVzVY0R3JYhbf0eOT0n0Y3kJz0R3JYhbf0eOT0n0",
            APP,
            now=NOW,
        )
    assert caught.value.reason == "bad_public_key"


@pytest.mark.parametrize(
    "token",
    ["", "nonsense", "v1.only-two", "v2.a.b", "v1.@@@.###"],
)
def test_malformed_tokens_are_rejected(token):
    with pytest.raises(TokenRejected) as caught:
        verify_token(token, PUBLIC_KEY, APP, now=NOW)
    assert caught.value.reason in {"missing_token", "malformed_token"}


def test_verification_uses_wall_clock_when_now_is_omitted():
    """With no injected clock a fresh lifetime token still verifies."""
    claims = verify_token(TOKENS["LIFETIME"], PUBLIC_KEY, APP)
    assert claims.status == "active"
    assert time.time() > claims.issued_at


# -- both verifier paths must agree -----------------------------------------
# cryptography is the verifier; the pure-Python path only exists for
# platforms where that compiled extension is absent (Android ships no
# cryptography wheel). It is not a second opinion — it must produce exactly
# the same verdict on every real token, or one platform would unlock a
# license the other rejects.


def _force_fallback(monkeypatch):
    monkeypatch.setattr("services.license_token._HAS_CRYPTOGRAPHY", False)


@pytest.mark.asyncio
async def test_compiled_verifier_is_in_use_on_this_platform():
    from services.license_token import using_cryptography

    assert using_cryptography() is True, "cryptography should be the verifier here"


@pytest.mark.parametrize(
    "name", ["LIFETIME", "YEARLY_ACTIVE", "GRACE", "EXPIRED", "REVOKED", "WRONG_APP"]
)
def test_fallback_agrees_with_cryptography(name, monkeypatch):
    compiled_outcome = _outcome(TOKENS[name])
    _force_fallback(monkeypatch)
    fallback_outcome = _outcome(TOKENS[name])
    assert fallback_outcome == compiled_outcome


def _outcome(token: str) -> tuple:
    try:
        claims = verify_token(token, PUBLIC_KEY, APP, now=NOW)
    except TokenRejected as ex:
        return ("rejected", ex.reason)
    return ("ok", claims.product, claims.status)
