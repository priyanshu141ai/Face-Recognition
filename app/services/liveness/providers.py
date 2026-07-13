from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json

from app.core.config import Settings
from app.services.liveness.base import LivenessProvider, LivenessResult


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class DisabledLivenessProvider(LivenessProvider):
    name = "disabled"

    def evaluate(self, frames, challenge, provider_assertion, capture_timestamp) -> LivenessResult:
        del frames, challenge, provider_assertion, capture_timestamp
        return LivenessResult(False, self.name, "liveness_disabled")


class MockLivenessProvider(LivenessProvider):
    name = "mock"

    def evaluate(self, frames, challenge, provider_assertion, capture_timestamp) -> LivenessResult:
        del provider_assertion, capture_timestamp
        approved = len(frames) >= int(challenge["required_capture_count"])
        return LivenessResult(approved, self.name, "mock_pass" if approved else "insufficient_frames")


class ExternalAssertionLivenessProvider(LivenessProvider):
    """Verifies a result assertion created by an external approved provider.

    This adapter does not perform anti-spoof inference and is only as strong as
    the separately evaluated service/SDK that creates the signed assertion.
    """

    name = "external_assertion"
    production_capable = True

    def __init__(self, secret: str) -> None:
        self._secret = secret.encode("utf-8")

    def evaluate(self, frames, challenge, provider_assertion, capture_timestamp) -> LivenessResult:
        del frames
        if not provider_assertion or provider_assertion.count(".") != 1:
            return LivenessResult(False, self.name, "liveness_assertion_missing")
        encoded, encoded_signature = provider_assertion.split(".", 1)
        expected = hmac.new(self._secret, encoded.encode("ascii"), hashlib.sha256).digest()
        try:
            signature = _b64url_decode(encoded_signature)
            payload = json.loads(_b64url_decode(encoded))
        except (ValueError, binascii.Error, json.JSONDecodeError, UnicodeDecodeError):
            return LivenessResult(False, self.name, "liveness_assertion_invalid")
        if not hmac.compare_digest(expected, signature):
            return LivenessResult(False, self.name, "liveness_assertion_invalid")
        expected_fields = {
            "challenge_id": challenge["challenge_id"],
            "user_id": challenge["user_id"],
            "device_id": challenge["device_id"],
            "challenge_type": challenge["challenge_type"],
            "capture_timestamp": capture_timestamp,
        }
        if any(payload.get(key) != value for key, value in expected_fields.items()):
            return LivenessResult(False, self.name, "liveness_assertion_scope_invalid")
        approved = payload.get("approved") is True
        return LivenessResult(approved, self.name, "provider_pass" if approved else "provider_reject")


def build_liveness_provider(settings: Settings) -> LivenessProvider:
    if settings.liveness_provider == "disabled":
        return DisabledLivenessProvider()
    if settings.liveness_provider == "mock":
        return MockLivenessProvider()
    if settings.liveness_provider == "external_assertion" and settings.liveness_assertion_secret:
        return ExternalAssertionLivenessProvider(settings.liveness_assertion_secret)
    return DisabledLivenessProvider()
