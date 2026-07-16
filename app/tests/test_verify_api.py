import base64
import os

import numpy as np
from fastapi.testclient import TestClient

os.environ.setdefault("DETECTOR_PROVIDER", "mock")

from app.main import app
from app.models.mock_recognizer import MockFaceRecognizer

client = TestClient(app)


def _png_bytes() -> bytes:
    import io
    from PIL import Image

    image = Image.new("RGB", (64, 64), color=(255, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_verify_endpoint_with_two_valid_images() -> None:
    payload = {
        "request_id": "req-1",
        "image_a": {"kind": "base64_png", "data": base64.b64encode(_png_bytes()).decode("ascii")},
        "image_b": {"kind": "base64_png", "data": base64.b64encode(_png_bytes()).decode("ascii")},
        "return_embeddings": False,
        "quality_policy": {"reject_if_no_face": True, "reject_if_multiple_faces": True, "min_detection_confidence": 0.85},
    }
    response = client.post("/v1/faces/verify", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["decision"] in {"match", "non_match"}
    assert body["match_score_percent"] >= 0
    assert body["similarity_cosine"] >= -1
    assert body["threshold"]["score_type"] == "cosine"
    assert "faces" in body and "timings_ms" in body


def test_verify_non_match_response_contract_is_unchanged(monkeypatch) -> None:
    embeddings = iter(
        [
            np.array([1.0, 0.0], dtype=np.float32),
            np.array([0.0, 1.0], dtype=np.float32),
        ]
    )
    monkeypatch.setattr(MockFaceRecognizer, "embed", lambda *_args: next(embeddings))
    response = client.post("/v1/faces/verify", json=_verify_payload("req-non-match"))
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-non-match"
    assert body["decision"] == "non_match"
    assert body["similarity_cosine"] == 0.0
    assert set(body) == {
        "request_id",
        "decision",
        "match_score_percent",
        "similarity_cosine",
        "threshold",
        "model_versions",
        "faces",
        "timings_ms",
    }


def _verify_payload(request_id: str) -> dict[str, object]:
    image = {"kind": "base64_png", "data": base64.b64encode(_png_bytes()).decode("ascii")}
    return {"request_id": request_id, "image_a": image, "image_b": image}
