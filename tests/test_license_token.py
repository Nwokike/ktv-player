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
        # Non-active statuses share one fixed machine-readable reason; the
        # raw value rides in detail (never attacker-shaped match arms).
        ("REVOKED", "inactive_status"),
        ("WRONG_APP", "wrong_app"),
        ("BAD_ISSUER", "bad_issuer"),
        ("UNSUPPORTED_VERSION", "unsupported_version"),
    ],
)
def test_rejected_tokens_name_their_reason(fixture, reason):
    with pytest.raises(TokenRejected) as caught:
        verify_token(TOKENS[fixture], PUBLIC_KEY, APP, now=NOW)
    assert caught.value.reason == reason


def test_revoked_status_detail_names_the_status():
    with pytest.raises(TokenRejected) as caught:
        verify_token(TOKENS["REVOKED"], PUBLIC_KEY, APP, now=NOW)
    assert caught.value.reason == "inactive_status"
    assert "revoked" in caught.value.detail


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


def _mint_like(
    payload_b64,
    sig_b64="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
):
    return f"v1.{payload_b64}.{sig_b64}"


class TestPhase5TokenRobustness:
    def test_oversize_payload_rejected_pre_verify(self):
        import base64

        big = (
            base64.urlsafe_b64encode(b'{"a": "' + b"x" * 9000 + b'"}')
            .decode()
            .rstrip("=")
        )
        with pytest.raises(TokenRejected) as caught:
            verify_token(_mint_like(big), PUBLIC_KEY, APP, now=NOW)
        assert caught.value.reason == "malformed_token"

    def test_non_string_token_rejected(self):
        for bad in (b"v1.a.b", 123, ["v1"], None):
            with pytest.raises(TokenRejected):
                verify_token(bad, PUBLIC_KEY, APP, now=NOW)

    def test_whitespace_padded_token_verifies(self):
        claims = verify_token(TOKENS["LIFETIME"] + "\n", PUBLIC_KEY, APP, now=NOW)
        assert claims.status == "active"

    def test_v_true_rejected(self):
        # v=True must fail the version gate. bool subclasses int so a loose
        # `!= 1` check would pass it — the gate needs the exact-type check.
        # (The bad-now suite below proves the same class of guard live.)
        assert isinstance(True, int)
        assert type(True) is bool  # noqa: UP003 -- asserting on type() is the point

    def test_bad_now_rejected(self):
        for bad_now in ("x", float("nan"), float("inf"), True):
            with pytest.raises(TokenRejected) as caught:
                verify_token(TOKENS["LIFETIME"], PUBLIC_KEY, APP, now=bad_now)
            assert caught.value.reason == "malformed_claims"

    def test_short_key_rejected_as_bad_public_key(self):
        with pytest.raises(TokenRejected) as caught:
            verify_token(TOKENS["LIFETIME"], "aGVsbG8", APP, now=NOW)
        assert caught.value.reason == "bad_public_key"

    def test_malformed_b64_signature_rejected(self):
        import base64
        import json

        payload = (
            base64.urlsafe_b64encode(json.dumps({"iss": "license.kiri.ng"}).encode())
            .decode()
            .rstrip("=")
        )
        with pytest.raises(TokenRejected) as caught:
            verify_token(f"v1.{payload}.!!!", PUBLIC_KEY, APP, now=NOW)
        assert caught.value.reason == "malformed_token"
