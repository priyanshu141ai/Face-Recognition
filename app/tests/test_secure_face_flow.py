import base64
import io
from datetime import datetime, timezone

import pytest
import numpy as np
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.rate_limit.factory import _cached


client = TestClient(app)
HEADERS = {
    "Authorization": "Bearer secret", "X-User-ID": "user-secure", "X-Device-ID": "phone-secure",
}


def _image(color):
    buffer = io.BytesIO()
    Image.new("RGB", (256, 256), color=color).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _enrollment(first, second, third):
    return {
        "enrollment_images": [
            {"angle": "front", "image": first},
            {"angle": "left", "image": second},
            {"angle": "right", "image": third},
        ]
    }


def _proof(private, challenge):
    signature = private.sign(challenge["canonical_payload"].encode(), ec.ECDSA(hashes.SHA256()))
    return {
        "challenge_id": challenge["challenge_id"], "nonce": challenge["nonce"],
        "signature": base64.b64encode(signature).decode(),
    }


def _device_challenge(operation):
    response = client.post(
        "/api/ess/device/challenge",
        json={"device_id": "phone-secure", "operation": operation}, headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _liveness(private, action, frames):
    device = _device_challenge("liveness_challenge")
    response = client.post(
        "/api/ess/liveness/challenge",
        json={"intended_action": action, "device_proof": _proof(private, device)}, headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    challenge = response.json()
    return {
        "challenge_id": challenge["challenge_id"], "challenge_nonce": challenge["nonce"],
        "capture_timestamp": datetime.now(timezone.utc).isoformat(),
        "challenge_action": challenge["challenge_type"], "frames": frames,
    }


@pytest.fixture(autouse=True)
def _environment(monkeypatch, tmp_path):
    _cached.cache_clear()
    monkeypatch.setenv("API_BEARER_TOKEN", "secret")
    monkeypatch.setenv("ESS_DATABASE_PATH", str(tmp_path / "secure-flow.sqlite3"))
    monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("DETECTOR_PROVIDER", "mock")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "mock")
    monkeypatch.setenv("DEVICE_PROOF_REQUIRED", "true")
    monkeypatch.setenv("ALLOW_LEGACY_DEVICE_ID_ONLY", "false")
    monkeypatch.setenv("LIVENESS_REQUIRED", "true")
    monkeypatch.setenv("LIVENESS_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_LEGACY_SINGLE_IMAGE_VERIFICATION", "false")
    monkeypatch.setattr(
        "app.models.mock_recognizer.MockFaceRecognizer.embed",
        lambda _self, _aligned: np.ones(16, dtype=np.float32),
    )
    for name in (
        "DEVICE_REGISTER_LIMIT_PER_HOUR", "DEVICE_VERIFY_LIMIT_PER_MINUTE",
        "LIVENESS_CHALLENGE_LIMIT_PER_MINUTE", "FACE_REGISTER_LIMIT_PER_HOUR",
        "FACE_VERIFY_LIMIT_PER_MINUTE",
    ):
        monkeypatch.setenv(name, "1000")


def test_face_enrollment_and_verify_require_device_proof_and_liveness() -> None:
    private = ec.generate_private_key(ec.SECP256R1())
    public = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    register = _device_challenge("register")
    response = client.post(
        "/api/ess/device/register",
        json={
            "device_id": "phone-secure", "platform": "android", "public_key": public,
            "device_proof": _proof(private, register),
        }, headers=HEADERS,
    )
    assert response.status_code == 201

    first, second, third = _image((20, 40, 60)), _image((21, 40, 60)), _image((22, 40, 60))
    face_proof = _device_challenge("face_register")
    enrolled = client.post(
        "/api/ess/face/register",
        json={
            **_enrollment(first, second, third),
            "liveness": _liveness(private, "face_register", [first, second, third]),
            "device_proof": _proof(private, face_proof), "consent_reference": "consent-001",
        }, headers=HEADERS,
    )
    assert enrolled.status_code == 201, enrolled.text

    missing = client.post("/api/ess/face/verify", json={"image": first}, headers=HEADERS)
    assert missing.status_code in {401, 422}

    face_verify = _device_challenge("face_verify")
    verified = client.post(
        "/api/ess/face/verify",
        json={
            "liveness": _liveness(
                private, "face_verify", [_image((23, 40, 60)), _image((24, 40, 60)), _image((25, 40, 60))]
            ),
            "device_proof": _proof(private, face_verify),
        }, headers=HEADERS,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["verified"] is True

    delete_challenge = _device_challenge("face_delete")
    deleted = client.post(
        "/api/ess/face/delete",
        json={
            "reason": "consent withdrawn",
            "device_proof": _proof(private, delete_challenge),
        }, headers=HEADERS,
    )
    assert deleted.status_code == 200
    assert client.get("/api/ess/face/status", headers=HEADERS).json()["registered"] is False

    re_enroll_proof = _device_challenge("face_register")
    re_enrollment = [_image((26, 40, 60)), _image((27, 40, 60)), _image((28, 40, 60))]
    re_enrolled = client.post(
        "/api/ess/face/register",
        json={
            **_enrollment(*re_enrollment),
            "liveness": _liveness(
                private, "face_register", re_enrollment
            ),
            "device_proof": _proof(private, re_enroll_proof),
            "consent_reference": "consent-002",
        }, headers=HEADERS,
    )
    assert re_enrolled.status_code == 201, re_enrolled.text
