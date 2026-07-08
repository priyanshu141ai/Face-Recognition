import base64
import os

from fastapi.testclient import TestClient

os.environ.setdefault("DETECTOR_PROVIDER", "mock")

from app.main import app

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
