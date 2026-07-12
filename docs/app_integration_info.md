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
POST /api/public/clients/validate
```

ESS integration endpoints:

```text
POST /api/clients
GET  /api/clients
POST /api/ess/device/register
POST /api/ess/device/verify
GET  /api/ess/device/status
POST /api/ess/device/reset
POST /api/ess/face/register
GET  /api/ess/face/status
POST /api/ess/face/verify
```

All ESS endpoints require `Authorization`. User-scoped endpoints additionally
require `X-User-ID`, populated only by the trusted login/API gateway. Device reset
also requires `X-Device-Reset-Token` from an admin/OTP recovery flow.

Required server configuration:

```text
ESS_DATABASE_PATH=data/ess.sqlite3
BIOMETRIC_ENCRYPTION_KEY=<Fernet key>
DEVICE_RESET_TOKEN=<admin recovery secret>
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
