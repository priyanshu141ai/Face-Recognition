import base64
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from sqlalchemy import update

from app.core.security_errors import SecurityDomainError
from app.persistence.schema import device_challenges
from app.schemas.liveness import DeviceProof
from app.services.device_proof import DeviceProofService, canonical_payload, validate_public_key
from app.services.ess_repository import EssRepository


def _key_pair():
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    return private, public


def _proof(private, challenge, nonce: str | None = None) -> DeviceProof:
    actual_nonce = nonce or challenge.nonce
    signature = private.sign(
        canonical_payload(challenge.__dict__, actual_nonce), ec.ECDSA(hashes.SHA256())
    )
    return DeviceProof(
        challenge_id=challenge.challenge_id,
        nonce=actual_nonce,
        signature=base64.b64encode(signature).decode("ascii"),
    )


def test_valid_signature_and_reused_nonce(tmp_path) -> None:
    repository = EssRepository(str(tmp_path / "db.sqlite3"))
    private, public = _key_pair()
    service = DeviceProofService(repository, 60)
    challenge = service.issue("user-a", "phone-001", "register")
    assert len(service.verify(
        _proof(private, challenge), user_id="user-a", device_id="phone-001",
        operation="register", public_key_pem=public
    )) == 64
    with pytest.raises(SecurityDomainError, match="already used") as reused:
        service.verify(
            _proof(private, challenge), user_id="user-a", device_id="phone-001",
            operation="register", public_key_pem=public
        )
    assert reused.value.code == "device_challenge_reused"


@pytest.mark.parametrize("field,value", [
    ("user_id", "user-b"), ("device_id", "phone-002"), ("operation", "verify")
])
def test_modified_signature_scope_is_rejected(tmp_path, field, value) -> None:
    repository = EssRepository(str(tmp_path / f"{field}.sqlite3"))
    private, public = _key_pair()
    service = DeviceProofService(repository, 60)
    challenge = service.issue("user-a", "phone-001", "register")
    arguments = {"user_id": "user-a", "device_id": "phone-001", "operation": "register"}
    arguments[field] = value
    with pytest.raises(SecurityDomainError) as error:
        service.verify(_proof(private, challenge), public_key_pem=public, **arguments)
    assert error.value.code == "device_proof_scope_invalid"


def test_wrong_key_expired_nonce_and_malformed_key_are_rejected(tmp_path) -> None:
    repository = EssRepository(str(tmp_path / "db.sqlite3"))
    private, public = _key_pair()
    wrong_private, _ = _key_pair()
    service = DeviceProofService(repository, 60)
    challenge = service.issue("user-a", "phone-001", "register")
    with pytest.raises(SecurityDomainError) as wrong:
        service.verify(
            _proof(wrong_private, challenge), user_id="user-a", device_id="phone-001",
            operation="register", public_key_pem=public
        )
    assert wrong.value.code == "device_signature_invalid"

    with repository.database.engine.begin() as connection:
        connection.execute(update(device_challenges).where(
            device_challenges.c.challenge_id == challenge.challenge_id
        ).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    with pytest.raises(SecurityDomainError) as expired:
        service.verify(
            _proof(private, challenge), user_id="user-a", device_id="phone-001",
            operation="register", public_key_pem=public
        )
    assert expired.value.code == "device_challenge_expired"

    with pytest.raises(SecurityDomainError):
        validate_public_key("not a public key")
    rsa_public = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    with pytest.raises(SecurityDomainError) as unsupported:
        validate_public_key(rsa_public)
    assert unsupported.value.code == "device_public_key_unsupported"
