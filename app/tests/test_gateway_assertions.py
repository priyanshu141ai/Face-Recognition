import time

import jwt
import pytest

from app.core.config import Settings
from app.core.security_errors import SecurityDomainError
from app.services.ess_repository import EssRepository
from app.services.gateway_assertions import GatewayAssertionService
from app.services.security_audit import SecurityAuditService
from app.tests.gateway_test_utils import TestGatewaySigner


def _service(tmp_path, signer, **overrides):
    jwks = tmp_path / f"{signer.kid}.jwks.json"
    signer.write_public_jwks(jwks)
    repository = EssRepository(str(tmp_path / "gateway.sqlite3"))
    repository.register_device("user-001", "device-0001", "android", None)
    values = {
        "gateway_assertion_required": True,
        "allow_unsigned_identity_headers": False,
        "gateway_assertion_issuer": "https://gateway.test",
        "gateway_assertion_audience": "face-api-test",
        "gateway_allowed_tenants": "tenant-001",
        "gateway_jwks_path": str(jwks),
        "gateway_assertion_max_ttl_seconds": 90,
        "gateway_jti_replay_ttl_seconds": 120,
        "allowed_attestation_app_identifiers": "com.example.ess",
    }
    values.update(overrides)
    settings = Settings(**values)
    return GatewayAssertionService(settings, repository, SecurityAuditService(repository, "audit-key")), repository


def _verify(service, token, **overrides):
    values = {
        "method": "GET",
        "path": "/api/ess/device/status",
        "request_id": "request-001",
        "expected_action": "device_status",
        "require_active_device": True,
    }
    values.update(overrides)
    return service.verify(token, **values)


def test_valid_assertion_is_accepted_once(tmp_path) -> None:
    signer = TestGatewaySigner()
    service, _ = _service(tmp_path, signer)
    token = signer.sign(action="device_status", path="/api/ess/device/status", request_id="request-001")
    assert _verify(service, token).user_id == "user-001"
    with pytest.raises(SecurityDomainError, match="already used") as replay:
        _verify(service, token)
    assert replay.value.code == "gateway_assertion_replayed"


@pytest.mark.parametrize(
    "claim,value,code",
    [
        ("iss", "https://wrong.test", "gateway_issuer_invalid"),
        ("aud", "wrong-api", "gateway_audience_invalid"),
        ("sub", "other-user", "gateway_claims_invalid"),
        ("tenant_id", "other-tenant", "gateway_tenant_mismatch"),
        ("action", "face_verify", "gateway_action_mismatch"),
        ("http_method", "POST", "gateway_request_mismatch"),
        ("request_path", "/wrong", "gateway_request_mismatch"),
        ("request_id", "wrong", "gateway_request_mismatch"),
        ("device_key_version", 2, "device_key_version_mismatch"),
    ],
)
def test_claim_and_request_mismatches_fail_closed(tmp_path, claim, value, code) -> None:
    signer = TestGatewaySigner()
    service, _ = _service(tmp_path, signer)
    values = {"action": "device_status", "path": "/api/ess/device/status", "request_id": "request-001"}
    values[claim] = value
    token = signer.sign(**values)
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, token)
    assert error.value.code == code


def test_expired_unknown_key_and_revoked_device_are_rejected(tmp_path) -> None:
    signer = TestGatewaySigner()
    service, repository = _service(tmp_path, signer)
    now = int(time.time())
    expired = signer.sign(
        action="device_status", path="/api/ess/device/status", request_id="request-001",
        iat=now - 120, nbf=now - 120, exp=now - 60,
    )
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, expired)
    assert error.value.code == "gateway_assertion_expired"

    untrusted = TestGatewaySigner("unknown-key").sign(
        action="device_status", path="/api/ess/device/status", request_id="request-001"
    )
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, untrusted)
    assert error.value.code == "gateway_key_unknown"

    repository.revoke_device("user-001", "device-0001")
    revoked = signer.sign(action="device_status", path="/api/ess/device/status", request_id="request-001")
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, revoked)
    assert error.value.code == "device_revoked"


def test_bad_signature_missing_claim_and_excessive_ttl_are_rejected(tmp_path) -> None:
    signer = TestGatewaySigner()
    service, _ = _service(tmp_path, signer)
    impostor = TestGatewaySigner(signer.kid)
    bad_signature = impostor.sign(action="device_status", path="/api/ess/device/status", request_id="request-001")
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, bad_signature)
    assert error.value.code == "gateway_assertion_invalid"

    now = int(time.time())
    excessive_ttl = signer.sign(
        action="device_status", path="/api/ess/device/status", request_id="request-001",
        iat=now, nbf=now, exp=now + 100,
    )
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, excessive_ttl)
    assert error.value.code == "gateway_claims_invalid"

    unsigned = jwt.encode(
        {"sub": "user-001", "exp": now + 60}, key="", algorithm="none", headers={"kid": signer.kid}
    )
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, unsigned)
    assert error.value.code == "gateway_algorithm_rejected"

    unexpected = jwt.encode(
        {"sub": "user-001", "exp": now + 60}, key="test-only-secret-with-32-bytes-min", algorithm="HS256",
        headers={"kid": signer.kid},
    )
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, unexpected)
    assert error.value.code == "gateway_algorithm_rejected"

    with pytest.raises(SecurityDomainError) as error:
        _verify(service, "malformed-test-assertion")
    assert error.value.code == "gateway_assertion_invalid"


def test_missing_jti_future_token_and_wrong_device_are_rejected(tmp_path) -> None:
    signer = TestGatewaySigner()
    service, _ = _service(tmp_path, signer)
    missing = signer.sign(
        action="device_status", path="/api/ess/device/status", request_id="request-001", _omit=("jti",)
    )
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, missing)
    assert error.value.code == "gateway_assertion_invalid"

    now = int(time.time())
    future = signer.sign(
        action="device_status", path="/api/ess/device/status", request_id="request-001",
        iat=now + 30, nbf=now + 30, exp=now + 60,
    )
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, future)
    assert error.value.code == "gateway_assertion_not_yet_valid"

    wrong_device = signer.sign(
        action="device_status", path="/api/ess/device/status", request_id="request-001",
        device_id="device-9999",
    )
    with pytest.raises(SecurityDomainError) as error:
        _verify(service, wrong_device)
    assert error.value.code == "device_not_registered"


def test_assertion_content_is_not_written_to_logs(caplog, tmp_path) -> None:
    signer = TestGatewaySigner()
    service, _ = _service(tmp_path, signer)
    token = TestGatewaySigner(signer.kid).sign(
        action="device_status", path="/api/ess/device/status", request_id="request-001"
    )
    with pytest.raises(SecurityDomainError):
        _verify(service, token)
    assert token not in caplog.text


def test_jwks_supports_overlapping_key_rotation(tmp_path) -> None:
    old, new = TestGatewaySigner("old-key"), TestGatewaySigner("new-key")
    jwks = tmp_path / "rotation.jwks.json"
    old.write_public_jwks(jwks, new)
    repository = EssRepository(str(tmp_path / "rotation.sqlite3"))
    repository.register_device("user-001", "device-0001", "android", None)
    settings = Settings(
        gateway_assertion_required=True,
        allow_unsigned_identity_headers=False,
        gateway_assertion_issuer="https://gateway.test",
        gateway_assertion_audience="face-api-test",
        gateway_allowed_tenants="tenant-001",
        gateway_jwks_path=str(jwks),
    )
    service = GatewayAssertionService(settings, repository, SecurityAuditService(repository, "audit-key"))
    for signer, request_id in ((old, "rotation-old"), (new, "rotation-new")):
        token = signer.sign(action="device_status", path="/api/ess/device/status", request_id=request_id)
        assert _verify(service, token, request_id=request_id).device_id == "device-0001"
