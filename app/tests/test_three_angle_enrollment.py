import base64
import io
import os
import sqlite3

import numpy as np
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app.main import app
from app.schemas.ess import FaceRegisterRequest
from app.core.errors import InvalidImagePayloadError
from app.models.mock_detector import MockFaceDetector
from app.models.mock_recognizer import MockFaceRecognizer
from app.services.biometric_crypto import BiometricCipher
from app.services.ess_repository import EssRepository
from app.services.image_decoder import ImageDecoder
from app.services.rate_limit.factory import _cached
import app.services.face_enrollment as face_enrollment


client = TestClient(app)
HEADERS = {
    "Authorization": "Bearer enrollment-test",
    "X-User-ID": "user-enrollment",
    "X-Device-ID": "phone-enrollment",
}


def _image(color=(20, 40, 60)) -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (256, 256), color).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _payload(image=None) -> dict[str, object]:
    image = image or _image()
    return {
        "request_id": "enrollment-001",
        "enrollment_images": [
            {"angle": angle, "image": image} for angle in ("front", "left", "right")
        ],
    }


def _padded_image() -> dict[str, str]:
    buffer, metadata = io.BytesIO(), PngInfo()
    metadata.add_text("padding", "x" * 4096)
    Image.new("RGB", (256, 256), (20, 40, 60)).save(buffer, format="PNG", pnginfo=metadata)
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


@pytest.fixture(autouse=True)
def _environment(monkeypatch, tmp_path) -> None:
    _cached.cache_clear()
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("API_BEARER_TOKEN", "enrollment-test")
    monkeypatch.setenv("ESS_DATABASE_PATH", str(tmp_path / "three-angle.sqlite3"))
    monkeypatch.setenv("BIOMETRIC_ENCRYPTION_KEY", key)
    monkeypatch.setenv("DETECTOR_PROVIDER", "mock")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_LEGACY_DEVICE_ID_ONLY", "true")
    monkeypatch.setenv("DEVICE_PROOF_REQUIRED", "false")
    monkeypatch.setenv("LIVENESS_REQUIRED", "false")
    monkeypatch.setenv("ALLOW_LEGACY_SINGLE_IMAGE_VERIFICATION", "true")
    monkeypatch.setenv("FACE_REGISTER_LIMIT_PER_HOUR", "1000")
    monkeypatch.setenv("DEVICE_REGISTER_LIMIT_PER_HOUR", "1000")
    monkeypatch.setattr(
        MockFaceRecognizer, "embed", lambda _self, _aligned: np.ones(16, dtype=np.float32)
    )
    response = client.post(
        "/api/ess/device/register",
        json={"device_id": "phone-enrollment", "platform": "android"},
        headers=HEADERS,
    )
    assert response.status_code == 201


def test_valid_enrollment_fuses_normalized_template_and_persists_only_safe_metadata() -> None:
    response = client.post("/api/ess/face/register", json=_payload(), headers=HEADERS)
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "registered"
    assert body["capture_count"] == 3
    assert body["captured_angles"] == ["front", "left", "right"]
    assert body["template_version"] == "three_angle_mean_l2_v1"
    assert "embedding" not in body and "enrollment_images" not in body

    with sqlite3.connect(os.environ["ESS_DATABASE_PATH"]) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(face_registrations)")}
        row = connection.execute(
            "SELECT encrypted_embedding, embedding_dimension, capture_count, captured_angles "
            "FROM face_registrations"
        ).fetchone()
    assert not ({"image", "images", "base64"} & columns)
    embedding = np.frombuffer(BiometricCipher(os.environ["BIOMETRIC_ENCRYPTION_KEY"]).decrypt(row[0]), dtype="<f4")
    assert embedding.size == row[1]
    assert np.linalg.norm(embedding) == pytest.approx(1.0, abs=1e-6)
    assert row[2:] == (3, "front,left,right")


@pytest.mark.parametrize(
    ("captures", "code"),
    [
        (["left", "right"], "invalid_enrollment_angles"),
        (["front", "right"], "invalid_enrollment_angles"),
        (["front", "left"], "invalid_enrollment_angles"),
        (["front", "front", "right"], "duplicate_enrollment_angle"),
        (["front", "left", "profile"], "invalid_enrollment_angles"),
    ],
)
def test_invalid_angle_sets_are_rejected(captures, code) -> None:
    payload = {
        "enrollment_images": [{"angle": angle, "image": _image()} for angle in captures]
    }
    response = client.post("/api/ess/face/register", json=payload, headers=HEADERS)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("none", "no_face_detected"),
        ("multiple", "multiple_faces_detected"),
        ("quality", "face_quality_rejected"),
    ],
)
def test_each_angle_gets_independent_quality_validation(monkeypatch, mode, code) -> None:
    original = MockFaceDetector.detect
    calls = 0

    def detect(self, image, quality_policy=None):
        nonlocal calls
        calls += 1
        detection = original(self, image, quality_policy)[0]
        if calls != 2:
            return [detection]
        if mode == "none":
            return []
        if mode == "multiple":
            return [detection, detection]
        return [detection.model_copy(update={"detection_confidence": 0.1})]

    monkeypatch.setattr(MockFaceDetector, "detect", detect)
    response = client.post("/api/ess/face/register", json=_payload(), headers=HEADERS)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code
    assert "left enrollment capture" in response.json()["detail"]["message"].lower()


def test_inconsistent_identity_is_rejected(monkeypatch) -> None:
    embeddings = iter(
        [
            np.array([1.0, 0.0, 0.0], dtype=np.float32),
            np.array([0.0, 1.0, 0.0], dtype=np.float32),
            np.array([0.0, 0.0, 1.0], dtype=np.float32),
        ]
    )
    monkeypatch.setattr(MockFaceRecognizer, "embed", lambda _self, _aligned: next(embeddings))
    response = client.post("/api/ess/face/register", json=_payload(), headers=HEADERS)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "enrollment_identity_mismatch"


def test_malformed_angle_stops_sequential_processing(monkeypatch) -> None:
    original = MockFaceDetector.detect
    calls = 0

    def detect(self, image, quality_policy=None):
        nonlocal calls
        calls += 1
        return original(self, image, quality_policy)

    monkeypatch.setattr(MockFaceDetector, "detect", detect)
    payload = _payload()
    payload["enrollment_images"][1]["image"] = {"kind": "base64_png", "data": "invalid-data"}
    response = client.post("/api/ess/face/register", json=payload, headers=HEADERS)
    assert response.status_code == 415
    assert "left enrollment capture" in response.json()["detail"]["message"].lower()
    assert calls == 1


@pytest.mark.parametrize(
    ("oversized_angles", "expected_detector_calls"),
    [(('left',), 1), (("front", "left", "right"), 0)],
)
def test_oversized_captures_stop_sequential_processing(
    monkeypatch, oversized_angles, expected_detector_calls
) -> None:
    monkeypatch.setenv("MAX_IMAGE_MB", "0.002")
    original = MockFaceDetector.detect
    calls = 0

    def detect(self, image, quality_policy=None):
        nonlocal calls
        calls += 1
        return original(self, image, quality_policy)

    monkeypatch.setattr(MockFaceDetector, "detect", detect)
    payload = _payload()
    for capture in payload["enrollment_images"]:
        if capture["angle"] in oversized_angles:
            capture["image"] = _padded_image()
    response = client.post("/api/ess/face/register", json=payload, headers=HEADERS)
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "invalid_image_payload"
    assert calls == expected_detector_calls


def test_three_angle_images_are_decoded_and_embedded_sequentially(monkeypatch) -> None:
    events = []

    def decode(_pipeline, _image, _max_image_mb, label):
        angle = label.split()[0]
        events.append(("decode", angle))
        return angle.encode("ascii")

    def extract(_pipeline, _image_bytes, _policy, _selector, _index, label):
        angle = label.split()[0]
        events.append(("embed", angle))
        return np.ones(3, dtype=np.float32) / np.sqrt(3.0)

    monkeypatch.setattr(face_enrollment, "_decode_image", decode)
    monkeypatch.setattr(face_enrollment, "_extract_embedding", extract)
    request = FaceRegisterRequest.model_validate(_payload())
    face_enrollment.extract_fused_face_template(request, 5.0)
    assert events == [
        ("decode", "front"),
        ("embed", "front"),
        ("decode", "left"),
        ("embed", "left"),
        ("decode", "right"),
        ("embed", "right"),
    ]


def test_three_angle_fusion_output_is_unchanged(monkeypatch) -> None:
    embeddings = iter(
        [
            np.array([1.0, 0.0, 0.0], dtype=np.float32),
            np.array([0.98, 0.2, 0.0], dtype=np.float32),
            np.array([0.98, -0.2, 0.0], dtype=np.float32),
        ]
    )
    monkeypatch.setattr(face_enrollment, "_decode_image", lambda *_args: b"image")
    monkeypatch.setattr(face_enrollment, "_extract_embedding", lambda *_args: next(embeddings))
    request = FaceRegisterRequest.model_validate(_payload())
    result = face_enrollment.extract_fused_face_template(request, 5.0)
    source = np.stack(
        [
            np.array([1.0, 0.0, 0.0], dtype=np.float32),
            np.array([0.98, 0.2, 0.0], dtype=np.float32),
            np.array([0.98, -0.2, 0.0], dtype=np.float32),
        ]
    )
    expected = np.mean(source, axis=0, dtype=np.float32)
    expected /= np.linalg.norm(expected)
    assert result.embedding == pytest.approx(expected, abs=1e-7)


def test_decompression_style_pixel_dimensions_are_rejected() -> None:
    buffer = io.BytesIO()
    Image.new("1", (5000, 5000)).save(buffer, format="PNG")
    payload = base64.b64encode(buffer.getvalue()).decode("ascii")
    with pytest.raises(InvalidImagePayloadError, match="pixel dimensions"):
        ImageDecoder(max_image_pixels=20_000_000).decode(payload, "base64_png")


def test_status_covers_not_registered_registered_and_revoked() -> None:
    empty = client.get("/api/ess/face/status", headers=HEADERS).json()
    assert (empty["registered"], empty["status"], empty["capture_count"]) == (False, "not_registered", 0)
    assert client.post("/api/ess/face/register", json=_payload(), headers=HEADERS).status_code == 201
    active = client.get("/api/ess/face/status", headers=HEADERS).json()
    assert (active["registered"], active["status"], active["capture_count"]) == (True, "registered", 3)
    EssRepository(os.environ["ESS_DATABASE_PATH"], initialize=False).revoke_face("user-enrollment")
    revoked = client.get("/api/ess/face/status", headers=HEADERS).json()
    assert (revoked["registered"], revoked["status"], revoked["capture_count"]) == (False, "revoked", 3)


def test_legacy_encrypted_template_remains_readable() -> None:
    embedding = np.ones(16, dtype=np.float32)
    embedding /= np.linalg.norm(embedding)
    encrypted = BiometricCipher(os.environ["BIOMETRIC_ENCRYPTION_KEY"]).encrypt(
        embedding.astype("<f4").tobytes()
    )
    EssRepository(os.environ["ESS_DATABASE_PATH"], initialize=False).register_face(
        "user-enrollment", encrypted, 16, "mock_yunet_adapter_v1",
        "mock_face_recognizer", "align112_rgb_v1",
    )
    status = client.get("/api/ess/face/status", headers=HEADERS).json()
    assert status["template_version"] == "single_capture_v1"
    assert status["capture_count"] == 1
    response = client.post("/api/ess/face/verify", json={"image": _image()}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["verified"] is True


def test_single_image_registration_is_rejected_even_with_development_verify_flag() -> None:
    response = client.post(
        "/api/ess/face/register", json={"image": _image()}, headers=HEADERS
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "invalid_enrollment_angles"


def test_invalid_payload_is_not_written_to_logs(caplog) -> None:
    marker = "not-valid-image-payload-marker"
    payload = _payload({"kind": "base64_png", "data": marker})
    assert client.post("/api/ess/face/register", json=payload, headers=HEADERS).status_code == 415
    assert marker not in caplog.text


def test_openapi_declares_exact_three_angle_contract() -> None:
    schema = app.openapi()
    request = schema["components"]["schemas"]["FaceRegisterRequest"]
    images = request["properties"]["enrollment_images"]
    assert images["minItems"] == images["maxItems"] == 3
    assert set(schema["components"]["schemas"]["EnrollmentAngle"]["enum"]) == {"front", "left", "right"}
    examples = schema["paths"]["/api/ess/face/register"]["post"]["responses"]["422"]["content"]["application/json"]["examples"]
    assert {"invalid_angles", "duplicate_angle", "quality_rejected", "identity_mismatch"} <= set(examples)
