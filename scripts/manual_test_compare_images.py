import argparse
import os

import httpx

from manual_api_common import image_payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image_a")
    parser.add_argument("image_b")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--token")
    args = parser.parse_args()

    token = args.token or os.getenv("API_BEARER_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    base = args.base_url.rstrip("/")
    body = {"request_id": "manual-compare", "image_a": image_payload(args.image_a), "image_b": image_payload(args.image_b)}
    with httpx.Client(headers=headers, timeout=60.0) as client:
        mode = client.get(f"{base}/v1/models/current").json()
        response = client.post(f"{base}/v1/faces/verify", json=body)

    print(f"detector={mode.get('detector', {}).get('name')}")
    print(f"recognizer={mode.get('recognizer', {}).get('name')}")
    print(f"status={response.status_code}")
    print(response.text)
    raise SystemExit(0 if response.status_code in {200, 422} else 1)


if __name__ == "__main__":
    main()
