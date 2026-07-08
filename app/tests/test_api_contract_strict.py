import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _png() -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (96, 96), color=(20, 40, 60)).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def test_models_current_mock_contract() -> None:
    data = client.get("/v1/models/current").json()
    assert data["detector"]["name"] == "mock_yunet_adapter_v1"
    assert data["recognizer"]["name"] == "mock_arcface_adapter_v1"
    assert data["recognizer"]["embedding_dim"] == 16


def test_verify_contract_hides_embeddings_by_default() -> None:
    response = client.post("/v1/faces/verify", json={"request_id": "strict", "image_a": _png(), "image_b": _png(), "return_embeddings": True})
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"request_id", "decision", "match_score_percent", "similarity_cosine", "threshold", "model_versions", "faces", "timings_ms"}
    assert "embeddings" not in data
    assert data["model_versions"]["detector"] == "mock_yunet_adapter_v1"


def test_detect_contract_face_schema() -> None:
    response = client.post("/v1/faces/detect", json={"request_id": "detect", "image": _png()})
    assert response.status_code == 200
    face = response.json()["faces"][0]
    assert set(face) == {"bbox_xywh", "landmarks5", "detection_confidence"}
    assert len(face["bbox_xywh"]) == 4
    assert len(face["landmarks5"]) == 5
