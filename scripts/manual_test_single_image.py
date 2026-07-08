import argparse
import base64
from pathlib import Path

import httpx


def _payload(path: Path) -> dict[str, str]:
    suffix = path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("Only .jpg/.jpeg/.png supported")
    kind = "base64_png" if suffix == ".png" else "base64_jpeg"
    return {"kind": kind, "data": base64.b64encode(path.read_bytes()).decode("ascii")}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_path")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token")
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    base = args.base_url.rstrip("/")
    with httpx.Client(headers=headers, timeout=30.0) as client:
        mode = client.get(f"{base}/v1/models/current").json()
        response = client.post(f"{base}/v1/faces/detect", json={"request_id": "manual-single", "image": _payload(Path(args.image_path))})

    print(f"detector={mode.get('detector', {}).get('name')}")
    print(f"recognizer={mode.get('recognizer', {}).get('name')}")
    print(f"status={response.status_code}")
    print(response.text)
    raise SystemExit(0 if response.status_code in {200, 422} else 1)


if __name__ == "__main__":
    main()
