from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ready_endpoint() -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["models_loaded"] is True
    assert body["provider"] == "mock"


def test_ready_fails_when_real_model_is_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DETECTOR_PROVIDER", "yunet")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "arcface_onnx")
    monkeypatch.setenv("YUNET_MODEL_PATH", str(tmp_path / "missing-yunet.onnx"))
    monkeypatch.setenv("ARCFACE_MODEL_PATH", str(tmp_path / "missing-arcface.onnx"))
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["models_loaded"] is False
