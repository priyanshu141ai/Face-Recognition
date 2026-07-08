import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _png() -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (96, 96), color=(80, 100, 120)).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _err(response) -> str:
    body = response.json()
    assert "detail" in body and "error" in body["detail"]
    assert "message" in body["detail"]["error"]
    return body["detail"]["error"]["code"]


def test_invalid_image_payload_error_shape() -> None:
    response = client.post("/v1/faces/verify", json={"request_id": "bad", "image_a": {"kind": "base64_png", "data": "bad"}, "image_b": _png()})
    assert response.status_code == 415
    assert _err(response) == "invalid_image_payload"


def test_invalid_detector_provider_error_shape(monkeypatch) -> None:
    monkeypatch.setenv("DETECTOR_PROVIDER", "bad_detector")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "mock")
    response = client.post("/v1/faces/verify", json={"request_id": "bad-detector", "image_a": _png(), "image_b": _png()})
    assert response.status_code == 500
    assert _err(response) == "detector_provider_invalid"


def test_invalid_recognizer_provider_error_shape(monkeypatch) -> None:
    monkeypatch.setenv("DETECTOR_PROVIDER", "mock")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "bad_recognizer")
    response = client.post("/v1/faces/verify", json={"request_id": "bad-recognizer", "image_a": _png(), "image_b": _png()})
    assert response.status_code == 500
    assert _err(response) == "recognizer_provider_invalid"


def test_arcface_model_missing_error_shape(monkeypatch) -> None:
    monkeypatch.setenv("DETECTOR_PROVIDER", "mock")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "arcface_onnx")
    monkeypatch.setenv("ARCFACE_MODEL_PATH", "models/missing-arcface.onnx")
    response = client.post("/v1/faces/verify", json={"request_id": "missing-arcface", "image_a": _png(), "image_b": _png()})
    assert response.status_code == 500
    assert _err(response) == "arcface_model_not_found"
