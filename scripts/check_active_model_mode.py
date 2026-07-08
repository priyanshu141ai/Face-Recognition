import argparse
import sys

import httpx


def _mode(data: dict[str, object]) -> str:
    detector = str(data.get("detector", {}).get("name", ""))
    recognizer = str(data.get("recognizer", {}).get("name", ""))
    dim = data.get("recognizer", {}).get("embedding_dim")
    if detector == "yunet_2023mar_opencv" and recognizer == "arcface_r100_onnx" and dim == 512:
        return "real"
    if "mock" in detector.lower() and "mock" in recognizer.lower():
        return "mock"
    return "mixed"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--expected", choices=["mock", "real"], required=True)
    args = parser.parse_args()

    url = f"{args.base_url.rstrip('/')}/v1/models/current"
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"FAIL: API not reachable at {url}: {exc}")
        raise SystemExit(1)

    active = _mode(data)
    print(f"active_mode={active}")
    print(f"detector={data.get('detector', {}).get('name')}")
    print(f"recognizer={data.get('recognizer', {}).get('name')}")
    print(f"embedding_dim={data.get('recognizer', {}).get('embedding_dim')}")

    if active != args.expected:
        print()
        print("PowerShell fix:")
        if args.expected == "real":
            print('$env:DETECTOR_PROVIDER="yunet"')
            print('$env:RECOGNIZER_PROVIDER="arcface_onnx"')
        else:
            print('$env:DETECTOR_PROVIDER="mock"')
            print('$env:RECOGNIZER_PROVIDER="mock"')
        print("python -m uvicorn app.main:app --reload")
        raise SystemExit(1)

    raise SystemExit(0)


if __name__ == "__main__":
    main()
