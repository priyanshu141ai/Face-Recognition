import argparse
import base64
import io
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
from PIL import Image


def _payload() -> dict[str, object]:
    buffer = io.BytesIO()
    Image.new("RGB", (96, 96), color=(80, 120, 160)).save(buffer, format="PNG")
    image = {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}
    return {"request_id": "perf", "image_a": image, "image_b": image}


def _one(base_url: str, headers: dict[str, str]) -> tuple[bool, float, int]:
    start = time.perf_counter()
    response = httpx.post(f"{base_url.rstrip('/')}/v1/faces/verify", json=_payload(), headers=headers, timeout=20.0)
    elapsed = (time.perf_counter() - start) * 1000.0
    ok = response.status_code in {200, 415, 422, 500} and "application/json" in response.headers.get("content-type", "")
    return ok, elapsed, response.status_code


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--requests", type=int, default=10)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--token")
    parser.add_argument("--warn-p95-ms", type=float, default=2500.0)
    args = parser.parse_args()

    token = args.token or os.getenv("API_BEARER_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(pool.map(lambda _: _one(args.base_url, headers), range(args.requests)))

    ok_count = sum(1 for ok, _, _ in results if ok)
    latencies = [elapsed for _, elapsed, _ in results]
    p50 = statistics.median(latencies)
    p95 = sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)]
    print(f"requests={args.requests} ok={ok_count} p50_ms={p50:.1f} p95_ms={p95:.1f} max_ms={max(latencies):.1f}")
    if ok_count != args.requests:
        raise SystemExit(1)
    raise SystemExit(2 if p95 > args.warn_p95_ms else 0)


if __name__ == "__main__":
    main()
