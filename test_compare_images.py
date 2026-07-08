import base64
import json
import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

IMAGE_A_PATH = "test_images/test_1.png"
IMAGE_B_PATH = "test_images/test_2.png"

def image_to_base64(path):
    image_bytes = Path(path).read_bytes()
    return base64.b64encode(image_bytes).decode("utf-8")

payload = {
    "request_id": "manual-compare-test-001",
    "image_a": {
        "kind": "base64_png",
        "data": image_to_base64(IMAGE_A_PATH)
    },
    "image_b": {
        "kind": "base64_png",
        "data": image_to_base64(IMAGE_B_PATH)
    },
    "face_selector": "largest",
    "return_embeddings": False,
    "quality_policy": {
        "reject_if_no_face": True,
        "reject_if_multiple_faces": True,
        "min_detection_confidence": 0.85
    }
}

response = requests.post(
    f"{BASE_URL}/v1/faces/verify",
    json=payload
)

print("Status Code:", response.status_code)
print(json.dumps(response.json(), indent=2))