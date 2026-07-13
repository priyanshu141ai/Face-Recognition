import base64
import io
import os
import sqlite3

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app


client = TestClient(app)


def _png(color: tuple[int, int, int] = (20, 40, 60)) -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (256, 256), color=color).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _enrollment(image: dict[str, str]) -> dict[str, object]:
    return {"enrollment_images": [{"angle": angle, "image": image} for angle in ("front", "left", "right")]}


@pytest.fixture(autouse=True)
def _ess_environment(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("API_BEARER_TOKEN", "api-secret")
    monkeypatch.setenv("ESS_DATABASE_PATH", str(tmp_path / "ess.sqlite3"))
    monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    monkeypatch.setenv("DEVICE_RESET_TOKEN", "reset-secret")
    monkeypatch.setenv("DETECTOR_PROVIDER", "mock")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_LEGACY_DEVICE_ID_ONLY", "true")
    monkeypatch.setenv("DEVICE_PROOF_REQUIRED", "false")
    monkeypatch.setenv("ALLOW_LEGACY_SINGLE_IMAGE_VERIFICATION", "true")
    monkeypatch.setenv("DEVICE_REGISTER_LIMIT_PER_HOUR", "1000")
    monkeypatch.setenv("DEVICE_VERIFY_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("FACE_VERIFY_LIMIT_PER_MINUTE", "1000")
    monkeypatch.setenv("FACE_REGISTER_LIMIT_PER_HOUR", "1000")


def _headers(user_id: str = "user-001", device_id: str = "phone-0001") -> dict[str, str]:
    return {
        "Authorization": "Bearer api-secret",
        "X-User-ID": user_id,
        "X-Device-ID": device_id,
    }


def _register_bound_device(user_id: str = "user-001", device_id: str = "phone-0001") -> None:
    response = client.post(
        "/api/ess/device/register",
        json={"device_id": device_id, "platform": "android"},
        headers=_headers(user_id, device_id),
    )
    assert response.status_code == 201


def test_client_management_is_protected_and_validation_is_public() -> None:
    payload = {"code": " acme-01 ", "name": "Acme Ltd"}
    assert client.post("/api/clients", json=payload).status_code == 401

    created = client.post("/api/clients", json=payload, headers=_headers())
    assert created.status_code == 201
    assert created.json()["code"] == "ACME-01"

    valid = client.post("/api/public/clients/validate", json={"code": "acme-01"})
    assert valid.status_code == 200
    assert valid.json()["valid"] is True
    assert valid.json()["client"]["name"] == "Acme Ltd"

    invalid = client.post("/api/public/clients/validate", json={"code": "missing"})
    assert invalid.status_code == 200
    assert invalid.json() == {"valid": False, "client": None}


def test_duplicate_client_code_is_rejected() -> None:
    payload = {"code": "CLIENT_A", "name": "Client A"}
    assert client.post("/api/clients", json=payload, headers=_headers()).status_code == 201
    response = client.post("/api/clients", json=payload, headers=_headers())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "client_code_exists"


def test_face_registration_is_encrypted_and_can_be_verified() -> None:
    _register_bound_device()
    image = _png()
    response = client.post("/api/ess/face/register", json=_enrollment(image), headers=_headers())
    assert response.status_code == 201
    assert response.json()["registered"] is True

    status_response = client.get("/api/ess/face/status", headers=_headers())
    assert status_response.status_code == 200
    assert status_response.json()["registered"] is True

    verify = client.post("/api/ess/face/verify", json={"image": image}, headers=_headers())
    assert verify.status_code == 200
    assert verify.json()["verified"] is True
    assert verify.json()["similarity_cosine"] == pytest.approx(1.0)

    with sqlite3.connect(os.environ["ESS_DATABASE_PATH"]) as connection:
        encrypted = connection.execute("SELECT encrypted_embedding FROM face_registrations").fetchone()[0]
    assert encrypted.startswith(b"gAAAA")

    duplicate = client.post("/api/ess/face/register", json=_enrollment(image), headers=_headers())
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "face_already_registered"


def test_face_registration_requires_user_identity() -> None:
    response = client.post(
        "/api/ess/face/register",
        json=_enrollment(_png()),
        headers={"Authorization": "Bearer api-secret"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "user_identity_required"


def test_face_endpoints_require_the_registered_device() -> None:
    response = client.get("/api/ess/face/status", headers=_headers())
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "device_not_authorized"

    _register_bound_device()
    allowed = client.get("/api/ess/face/status", headers=_headers())
    assert allowed.status_code == 200


def test_device_binding_blocks_second_phone_and_other_user() -> None:
    first = {"device_id": "phone-0001", "platform": "android"}
    response = client.post("/api/ess/device/register", json=first, headers=_headers())
    assert response.status_code == 201
    assert response.json()["already_registered"] is False

    idempotent = client.post("/api/ess/device/register", json=first, headers=_headers())
    assert idempotent.status_code == 201
    assert idempotent.json()["already_registered"] is True

    second_phone = client.post(
        "/api/ess/device/register",
        json={"device_id": "phone-0002", "platform": "android"},
        headers=_headers(),
    )
    assert second_phone.status_code == 409
    assert second_phone.json()["detail"]["code"] == "user_device_conflict"

    other_user = client.post("/api/ess/device/register", json=first, headers=_headers("user-002"))
    assert other_user.status_code == 409
    assert other_user.json()["detail"]["code"] == "device_user_conflict"

    assert client.post("/api/ess/device/verify", json={"device_id": "phone-0001"}, headers=_headers()).status_code == 200
    denied = client.post("/api/ess/device/verify", json={"device_id": "phone-0002"}, headers=_headers())
    assert denied.status_code == 403


def test_device_reset_needs_recovery_authorization() -> None:
    assert client.post(
        "/api/ess/device/register",
        json={"device_id": "phone-old1", "platform": "ios"},
        headers=_headers(),
    ).status_code == 201

    denied = client.post(
        "/api/ess/device/reset",
        json={"reason": "new phone"},
        headers={**_headers(), "X-Device-Reset-Token": "wrong"},
    )
    assert denied.status_code == 403

    reset = client.post(
        "/api/ess/device/reset",
        json={"reason": "new phone"},
        headers={**_headers(), "X-Device-Reset-Token": "reset-secret"},
    )
    assert reset.status_code == 200
    assert reset.json()["reset"] is True

    replacement = client.post(
        "/api/ess/device/register",
        json={"device_id": "phone-new1", "platform": "ios"},
        headers=_headers(),
    )
    assert replacement.status_code == 201


def test_ess_openapi_has_typed_responses_and_device_header() -> None:
    schema = app.openapi()
    register = schema["paths"]["/api/ess/face/register"]["post"]
    response_schema = register["responses"]["201"]["content"]["application/json"]["schema"]
    assert response_schema["$ref"].endswith("/FaceRegisterResponse")
    assert "X-Device-ID" in {parameter["name"] for parameter in register["parameters"]}
