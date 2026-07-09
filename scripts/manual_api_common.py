import base64
from pathlib import Path


def image_payload(path: str) -> dict[str, str]:
    image_path = Path(path)
    suffix = image_path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("Only .jpg/.jpeg/.png supported")
    return {
        "kind": "base64_png" if suffix == ".png" else "base64_jpeg",
        "data": base64.b64encode(image_path.read_bytes()).decode("ascii"),
    }
