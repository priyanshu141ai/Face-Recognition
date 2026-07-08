import base64
import logging

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_invalid_base64_image_returns_415() -> None:
    payload = {
        "image_a": {"kind": "base64_png", "data": "not-base64"},
        "image_b": {"kind": "base64_png", "data": base64.b64encode(b"abc").decode("ascii")},
    }
    response = client.post("/v1/faces/verify", json=payload)
    assert response.status_code == 415


def test_logs_do_not_contain_raw_image_payloads(caplog) -> None:
    payload = {
        "request_id": "log-test",
        "image_a": {"kind": "base64_png", "data": base64.b64encode(b"abc").decode("ascii")},
        "image_b": {"kind": "base64_png", "data": base64.b64encode(b"abc").decode("ascii")},
    }
    caplog.set_level(logging.INFO, logger="face_recognition_backend")
    response = client.post("/v1/faces/verify", json=payload)
    assert response.status_code == 415
    messages = " ".join(record.getMessage() for record in caplog.records)
    assert "base64" not in messages.lower()
    assert "data:image" not in messages.lower()
