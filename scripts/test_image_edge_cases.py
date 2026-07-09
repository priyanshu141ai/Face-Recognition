import argparse
import base64
import io
import os
import sys

import httpx
from PIL import Image


def _img(mode: str, fmt: str, size: tuple[int, int] = (96, 96)) -> dict[str, str]:
    color = 120 if mode == "L" else ((120, 80, 40, 180) if mode == "RGBA" else (120, 80, 40))
    buffer = io.BytesIO()
    Image.new(mode, size, color=color).save(buffer, format=fmt)
    return {"kind": f"base64_{'jpeg' if fmt == 'JPEG' else 'png'}", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _post(client: httpx.Client, url: str, payload: dict[str, object]) -> tuple[int, str]:
    try:
        response = client.post(url, json=payload, timeout=10.0)
        body = response.text[:400].lower()
        json_ok = "application/json" in response.headers.get("content-type", "")
        if "traceback" in body or (response.status_code >= 500 and not json_ok):
            return response.status_code, "FAIL"
        return response.status_code, "PASS"
    except Exception as exc:
        return 0, f"FAIL {exc}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token")
    args = parser.parse_args()

    token = args.token or os.getenv("API_BEARER_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    base = args.base_url.rstrip("/")
    cases = [
        ("valid_png_verify", f"{base}/v1/faces/verify", {"request_id": "edge-png", "image_a": _img("RGB", "PNG"), "image_b": _img("RGB", "PNG")}, {200, 422}),
        ("valid_jpeg_detect", f"{base}/v1/faces/detect", {"request_id": "edge-jpeg", "image": _img("RGB", "JPEG")}, {200, 422}),
        ("rgba_png_detect", f"{base}/v1/faces/detect", {"request_id": "edge-rgba", "image": _img("RGBA", "PNG")}, {200, 422}),
        ("gray_png_detect", f"{base}/v1/faces/detect", {"request_id": "edge-gray", "image": _img("L", "PNG")}, {200, 422}),
        ("kind_mismatch", f"{base}/v1/faces/detect", {"request_id": "edge-mismatch", "image": {**_img("RGB", "PNG"), "kind": "base64_jpeg"}}, {415}),
        ("bad_base64", f"{base}/v1/faces/detect", {"request_id": "edge-bad64", "image": {"kind": "base64_png", "data": "bad"}}, {415}),
        ("empty_payload", f"{base}/v1/faces/detect", {"request_id": "edge-empty", "image": {"kind": "base64_png", "data": ""}}, {415, 422}),
        ("random_bytes", f"{base}/v1/faces/detect", {"request_id": "edge-random", "image": {"kind": "base64_png", "data": base64.b64encode(b"not-image").decode("ascii")}}, {415}),
    ]

    failures = 0
    with httpx.Client(headers=headers) as client:
        for name, url, payload, expected in cases:
            status, result = _post(client, url, payload)
            ok = status in expected and result == "PASS"
            failures += 0 if ok else 1
            print(f"{name}: status={status} expected={sorted(expected)} result={'PASS' if ok else result}")

    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
