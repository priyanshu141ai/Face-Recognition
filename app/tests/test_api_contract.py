import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.validation.checks import check_api_response_shape, check_error_response_shape

client = TestClient(app)


def _png_payload() -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color=(10, 20, 30)).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def test_verify_response_schema_contains_required_fields() -> None:
    response = client.post("/v1/faces/verify", json={"request_id": "contract", "image_a": _png_payload(), "image_b": _png_payload()})
    assert response.status_code == 200
    assert check_api_response_shape(response.json()).status == "PASS"


def test_error_response_schema_is_consistent() -> None:
    response = client.post(
        "/v1/faces/verify",
        json={"request_id": "bad", "image_a": {"kind": "base64_png", "data": "bad"}, "image_b": _png_payload()},
    )
    assert response.status_code == 415
    assert check_error_response_shape(response.json()).status in {"PASS", "WARN"}
