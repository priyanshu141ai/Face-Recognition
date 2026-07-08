import base64
import io
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.models.arcface_onnx_recognizer import ArcFaceOnnxRecognizer
from app.models.yunet_detector import YuNetFaceDetector

ROOT = Path(__file__).resolve().parents[2]
YUNET = ROOT / "models/face_detection_yunet_2023mar.onnx"
ARCFACE = ROOT / "models/face-recognition-resnet100-arcface.onnx"


def _require_real() -> None:
    if not YUNET.exists() or not ARCFACE.exists():
        pytest.skip("real ONNX model files are not available")


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (160, 160), color=(0, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_yunet_real_detector_initializes_and_returns_schema(monkeypatch) -> None:
    _require_real()
    monkeypatch.setenv("DETECTOR_PROVIDER", "yunet")
    monkeypatch.setenv("YUNET_MODEL_PATH", str(YUNET))
    detections = YuNetFaceDetector().detect(_png_bytes())
    assert isinstance(detections, list)


def test_arcface_real_recognizer_embedding_contract(monkeypatch) -> None:
    _require_real()
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "arcface_onnx")
    monkeypatch.setenv("ARCFACE_MODEL_PATH", str(ARCFACE))
    embedding = ArcFaceOnnxRecognizer().embed(np.zeros((112, 112, 3), dtype=np.uint8))
    assert embedding.shape == (512,)
    assert np.isfinite(embedding).all()
    assert np.linalg.norm(embedding) == pytest.approx(1.0, abs=1e-4)


def test_real_api_blank_image_fails_cleanly(monkeypatch) -> None:
    _require_real()
    monkeypatch.setenv("DETECTOR_PROVIDER", "yunet")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "arcface_onnx")
    monkeypatch.setenv("YUNET_MODEL_PATH", str(YUNET))
    monkeypatch.setenv("ARCFACE_MODEL_PATH", str(ARCFACE))
    payload = {"kind": "base64_png", "data": base64.b64encode(_png_bytes()).decode("ascii")}
    response = TestClient(app).post("/v1/faces/verify", json={"request_id": "real-clean", "image_a": payload, "image_b": payload})
    assert response.status_code == 422
    assert response.json()["detail"]["error"]["code"] == "no_face_detected"
