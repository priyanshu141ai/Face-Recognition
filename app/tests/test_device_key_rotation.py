import base64

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
HEADERS = {"Authorization": "Bearer secret", "X-User-ID": "user-001"}


def _keys():
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode("ascii")
    return private, public


def _challenge(operation: str):
    response = client.post(
        "/api/ess/device/challenge",
        json={"device_id": "phone-001", "operation": operation}, headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _proof(private, challenge):
    signature = private.sign(challenge["canonical_payload"].encode("utf-8"), ec.ECDSA(hashes.SHA256()))
    return {
        "challenge_id": challenge["challenge_id"],
        "nonce": challenge["nonce"],
        "signature": base64.b64encode(signature).decode("ascii"),
    }


@pytest.fixture(autouse=True)
def _environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("API_BEARER_TOKEN", "secret")
    monkeypatch.setenv("ESS_DATABASE_PATH", str(tmp_path / "secure.sqlite3"))
    monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("DEVICE_PROOF_REQUIRED", "true")
    monkeypatch.setenv("ALLOW_LEGACY_DEVICE_ID_ONLY", "false")
    monkeypatch.setenv("DEVICE_REGISTER_LIMIT_PER_HOUR", "1000")
    monkeypatch.setenv("DEVICE_VERIFY_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("DEVICE_ROTATE_LIMIT_PER_HOUR", "1000")
    monkeypatch.setenv("DEVICE_REVOKE_LIMIT_PER_HOUR", "1000")


def test_key_rotation_invalidates_old_key_and_revoke_blocks_device() -> None:
    old_private, old_public = _keys()
    new_private, new_public = _keys()
    register_challenge = _challenge("register")
    registered = client.post(
        "/api/ess/device/register",
        json={
            "device_id": "phone-001", "platform": "android", "public_key": old_public,
            "device_proof": _proof(old_private, register_challenge),
        },
        headers=HEADERS,
    )
    assert registered.status_code == 201

    copied_id = _challenge("verify")
    missing = client.post(
        "/api/ess/device/verify", json={"device_id": "phone-001"}, headers=HEADERS
    )
    assert missing.status_code == 401
    assert missing.json()["detail"]["code"] == "device_proof_required"

    rotate_challenge = _challenge("rotate")
    rotated = client.post(
        "/api/ess/device/rotate",
        json={
            "device_id": "phone-001", "new_public_key": new_public,
            "device_proof": _proof(old_private, rotate_challenge),
        },
        headers=HEADERS,
    )
    assert rotated.status_code == 200
    assert rotated.json()["key_version"] == 2

    verify_challenge = _challenge("verify")
    old_key = client.post(
        "/api/ess/device/verify",
        json={"device_id": "phone-001", "device_proof": _proof(old_private, verify_challenge)},
        headers=HEADERS,
    )
    assert old_key.status_code == 403
    verified = client.post(
        "/api/ess/device/verify",
        json={"device_id": "phone-001", "device_proof": _proof(new_private, verify_challenge)},
        headers=HEADERS,
    )
    assert verified.status_code == 200

    revoke_challenge = _challenge("revoke")
    revoked = client.post(
        "/api/ess/device/revoke",
        json={
            "device_id": "phone-001", "reason": "user requested replacement",
            "device_proof": _proof(new_private, revoke_challenge),
        },
        headers=HEADERS,
    )
    assert revoked.status_code == 200
    assert client.post(
        "/api/ess/device/challenge",
        json={"device_id": "phone-001", "operation": "verify"}, headers=HEADERS,
    ).status_code == 403
