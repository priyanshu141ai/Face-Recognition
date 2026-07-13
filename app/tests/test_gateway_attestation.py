import time

import pytest

from app.core.security_errors import SecurityDomainError
from app.tests.gateway_test_utils import TestGatewaySigner
from app.tests.test_gateway_assertions import _service, _verify


def _attestation(**overrides):
    value = {
        "provider": "play_integrity",
        "verdict": "MEETS_DEVICE_INTEGRITY",
        "checked_at": int(time.time()),
        "app_identifier": "com.example.ess",
        "platform": "android",
    }
    value.update(overrides)
    return value


def test_valid_recent_attestation_is_accepted(tmp_path) -> None:
    signer = TestGatewaySigner()
    service, _ = _service(tmp_path, signer, require_recent_device_attestation=True)
    token = signer.sign(
        action="device_status", path="/api/ess/device/status", request_id="request-001",
        device_attestation=_attestation(),
    )
    assert _verify(service, token).device_attestation.provider == "play_integrity"


@pytest.mark.parametrize(
    "attestation,code",
    [
        (None, "device_attestation_required"),
        (_attestation(checked_at=int(time.time()) - 1000), "device_attestation_stale"),
        (_attestation(app_identifier="com.attacker.app"), "device_attestation_app_invalid"),
        (_attestation(verdict="FAILED"), "device_attestation_rejected"),
        (_attestation(provider="app_attest"), "device_attestation_provider_invalid"),
    ],
)
def test_attestation_policy_fails_closed(tmp_path, attestation, code) -> None:
    signer = TestGatewaySigner()
    service, _ = _service(tmp_path, signer, require_recent_device_attestation=True)
    token = signer.sign(
        action="device_status", path="/api/ess/device/status", request_id="request-001",
        device_attestation=attestation,
    )
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, token)
    assert error.value.code == code
