import base64
import json
import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"

IMAGE_PATH = "test_images/priyanshu.png"

def image_to_base64(path):
    image_bytes = Path(path).read_bytes()
    return base64.b64encode(image_bytes).decode("utf-8")

payload = {
    "image": {
        "kind": "base64_png",
        "data": image_to_base64(IMAGE_PATH)
    },
    "min_face_score": 0.85
}

response = requests.post(
    f"{BASE_URL}/v1/faces/detect",
    json=payload
)

print("Status Code:", response.status_code)
print(json.dumps(response.json(), indent=2))