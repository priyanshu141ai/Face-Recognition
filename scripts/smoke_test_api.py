import argparse
import base64
import io
import os
import sys
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.validation.checks import check_api_response_shape, check_error_response_shape
from app.validation.report import ValidationReport, ValidationResult


def _image_payload(color: tuple[int, int, int]) -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (96, 96), color=color).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _headers() -> dict[str, str]:
    token = os.getenv("API_BEARER_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _controlled_error(data: dict[str, Any]) -> bool:
    detail = data.get("detail", data)
    return isinstance(detail, dict) and isinstance(detail.get("error"), dict)


def _add_endpoint_result(report: ValidationReport, endpoint: str, code: int, ok: bool, notes: str) -> None:
    report.add(ValidationResult(endpoint, "API", "PASS" if ok else "FAIL", f"HTTP {code} - {notes}"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    report = ValidationReport()
    client = httpx.Client(base_url=args.base_url, headers=_headers(), timeout=10.0)
    image_a = _image_payload((255, 0, 0))
    image_b = _image_payload((0, 255, 0))

    try:
        response = client.get("/healthz")
        _add_endpoint_result(report, "GET /healthz", response.status_code, response.status_code == 200 and response.json().get("status") == "ok", "status ok")

        response = client.get("/readyz")
        body = response.json()
        _add_endpoint_result(report, "GET /readyz", response.status_code, response.status_code < 500 and body.get("status") in {"ready", "not_ready"}, "controlled response")

        response = client.get("/v1/models/current")
        body = response.json()
        expected = {"detector", "recognizer", "preprocessing", "threshold", "calibration"}
        _add_endpoint_result(report, "GET /v1/models/current", response.status_code, response.status_code == 200 and expected <= body.keys(), "metadata shape")

        response = client.post("/v1/faces/detect", json={"request_id": "smoke-detect", "image": image_a})
        detect_body = response.json()
        _add_endpoint_result(report, "POST /v1/faces/detect", response.status_code, response.status_code == 200 or (response.status_code in {422, 500} and _controlled_error(detect_body)), "valid or controlled error")

        verify_payload = {"request_id": "smoke-verify", "image_a": image_a, "image_b": image_b}
        response = client.post("/v1/faces/verify", json=verify_payload)
        verify_body = response.json()
        if response.status_code == 200:
            shape = check_api_response_shape(verify_body)
            report.add(shape)
            verify_ok = shape.status == "PASS"
        else:
            err = check_error_response_shape(verify_body)
            report.add(err)
            verify_ok = response.status_code in {415, 422, 500} and err.status in {"PASS", "WARN"}
        _add_endpoint_result(report, "POST /v1/faces/verify", response.status_code, verify_ok, "valid or controlled error")

        bad_payload = {"image_a": {"kind": "base64_png", "data": "not-base64"}, "image_b": image_b}
        response = client.post("/v1/faces/verify", json=bad_payload)
        body = response.json()
        err = check_error_response_shape(body)
        report.add(err)
        _add_endpoint_result(report, "Invalid base64", response.status_code, response.status_code in {415, 422} and err.status in {"PASS", "WARN"}, "controlled error")
    except Exception as exc:
        report.add(ValidationResult("API smoke test", "API", "FAIL", str(exc)))
    finally:
        client.close()

    report.print_table()
    raise SystemExit(0 if report.overall_status == "PASS" else 1)


if __name__ == "__main__":
    main()
