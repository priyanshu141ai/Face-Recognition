import argparse
import base64
import io

import httpx
from PIL import Image


def _image_payload() -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (96, 96), color=(30, 60, 90)).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _post_verify(client: httpx.Client, headers: dict[str, str] | None = None) -> httpx.Response:
    image = _image_payload()
    return client.post("/v1/faces/verify", json={"request_id": "auth-check", "image_a": image, "image_b": image}, headers=headers)


def _post_detect(client: httpx.Client, headers: dict[str, str] | None = None) -> httpx.Response:
    return client.post("/v1/faces/detect", json={"request_id": "auth-check", "image": _image_payload()}, headers=headers)


def _row(name: str, ok: bool, http_code: int, notes: str) -> list[str]:
    return [name, "PASS" if ok else "FAIL", str(http_code), notes]


def _print(rows: list[list[str]]) -> None:
    headers = ["Check", "Status", "HTTP", "Notes"]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(widths[index], len(cell)) for index, cell in enumerate(row)]

    def fmt(row: list[str]) -> str:
        return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))

    print(fmt(headers))
    print(fmt(["-" * width for width in widths]))
    for row in rows:
        print(fmt(row))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token", required=True)
    args = parser.parse_args()

    ok_headers = {"Authorization": f"Bearer {args.token}"}
    bad_headers = {"Authorization": "Bearer wrong-token"}
    rows: list[list[str]] = []
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=20.0) as client:
        response = client.get("/healthz")
        rows.append(_row("healthz public", response.status_code == 200, response.status_code, "ok"))

        response = client.get("/v1/models/current")
        rows.append(_row("models/current no token", response.status_code == 401, response.status_code, "protected"))

        response = client.get("/v1/models/current", headers=bad_headers)
        rows.append(_row("models/current wrong token", response.status_code == 401, response.status_code, "protected"))

        response = client.get("/v1/models/current", headers=ok_headers)
        rows.append(_row("models/current correct token", response.status_code == 200, response.status_code, "authorized"))

        response = _post_detect(client)
        rows.append(_row("faces/detect no token", response.status_code == 401, response.status_code, "protected"))

        response = _post_verify(client)
        rows.append(_row("faces/verify no token", response.status_code == 401, response.status_code, "protected"))

        response = _post_verify(client, ok_headers)
        rows.append(_row("faces/verify correct token", response.status_code in {200, 415, 422, 500}, response.status_code, "authorized path reached"))

    _print(rows)
    raise SystemExit(0 if all(row[1] == "PASS" for row in rows) else 1)


if __name__ == "__main__":
    main()
