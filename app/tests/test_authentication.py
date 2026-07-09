import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def _png() -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color=(20, 40, 60)).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _verify_payload() -> dict[str, object]:
    image = _png()
    return {"request_id": "auth-test", "image_a": image, "image_b": image}


def test_auth_disabled_allows_local_models_current(monkeypatch) -> None:
    monkeypatch.delenv("API_BEARER_TOKEN", raising=False)
    assert client.get("/v1/models/current").status_code == 200


def test_healthz_remains_public_when_auth_enabled(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKEN", "secret-token")
    assert client.get("/healthz").status_code == 200


def test_models_current_requires_token_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKEN", "secret-token")
    assert client.get("/v1/models/current").status_code == 401
    assert client.get("/v1/models/current", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/v1/models/current", headers={"Authorization": "Bearer secret-token"}).status_code == 200


def test_face_endpoints_require_token_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKEN", "secret-token")
    assert client.post("/v1/faces/detect", json={"image": _png()}).status_code == 401
    assert client.post("/v1/faces/embed", json={"image": _png()}).status_code == 401
    assert client.post("/v1/faces/verify", json=_verify_payload()).status_code == 401


def test_correct_token_reaches_verify_endpoint(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKEN", "secret-token")
    response = client.post("/v1/faces/verify", json=_verify_payload(), headers={"Authorization": "Bearer secret-token"})
    assert response.status_code == 200


def test_token_is_not_returned_in_auth_errors(monkeypatch) -> None:
    monkeypatch.setenv("API_BEARER_TOKEN", "secret-token")
    response = client.get("/v1/models/current", headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401
    assert "secret-token" not in response.text
    assert "wrong" not in response.text
