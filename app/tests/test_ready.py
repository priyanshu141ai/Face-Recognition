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
