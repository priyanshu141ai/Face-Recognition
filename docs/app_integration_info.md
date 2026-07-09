# App Integration Info

## 1. Base URL

```text
http://127.0.0.1:8000
```

## 2. Authorization Token

Send this header on protected endpoints:

```text
Authorization: Bearer my-secret-token
```

## 3. Endpoint URLs

```text
GET  /healthz
GET  /readyz
GET  /v1/models/current
POST /v1/faces/detect
POST /v1/faces/verify
POST /v1/faces/embed
```

Protected:

```text
GET  /v1/models/current
POST /v1/faces/detect
POST /v1/faces/verify
POST /v1/faces/embed
```

Public:

```text
GET /healthz
GET /readyz
```

## 4. Request Body Format

### Detect

```json
{
  "request_id": "req-001",
  "image": {
    "kind": "base64_png",
    "data": "<base64-image>"
  }
}
```

### Verify

```json
{
  "request_id": "req-001",
  "image_a": {
    "kind": "base64_png",
    "data": "<base64-image-a>"
  },
  "image_b": {
    "kind": "base64_png",
    "data": "<base64-image-b>"
  },
  "face_selector": "largest",
  "return_embeddings": false
}
```

Allowed image kinds:

```text
base64_png
base64_jpeg
```

## 5. Response Format

### Verify Success

```json
{
  "request_id": "req-001",
  "decision": "match",
  "match_score_percent": 82.16,
  "similarity_cosine": 0.821604,
  "threshold": {
    "score_type": "cosine",
    "value": 0.4,
    "operating_point": "phase3_fixed_threshold"
  },
  "model_versions": {
    "detector": "yunet_2023mar_opencv",
    "recognizer": "arcface_r100_onnx",
    "preprocessing": "align112_rgb_v1",
    "calibration": "linear_mock_v1"
  },
  "faces": {
    "image_a": [],
    "image_b": []
  },
  "timings_ms": {}
}
```

### Error

```json
{
  "detail": {
    "request_id": "req-001",
    "error": {
      "code": "no_face_detected",
      "message": "no face detected in image_a"
    }
  }
}
```
