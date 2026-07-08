import base64
import io
import logging

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.validation.checks import check_no_sensitive_logging_patterns

client = TestClient(app)


def _payload() -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), color=(1, 2, 3)).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def test_logs_do_not_contain_sensitive_payloads(caplog) -> None:
    caplog.set_level(logging.INFO)
    response = client.post("/v1/faces/verify", json={"request_id": "safe-log", "image_a": _payload(), "image_b": _payload()})
    assert response.status_code == 200
    log_text = " ".join(record.getMessage() for record in caplog.records)
    assert check_no_sensitive_logging_patterns(log_text).status == "PASS"
