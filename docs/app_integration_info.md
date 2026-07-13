# App Integration Guide

This document defines the mobile/ESS integration workflow for client validation,
device binding, face enrollment, and registered-face verification.

## 1. Architecture and Trust Boundary

Recommended production flow:

```text
Mobile App --user JWT--> ESS Backend/Gateway
ESS Backend --service bearer token + trusted X-User-ID--> Face API
```

The Face API currently validates a shared service bearer token. It does not
validate the mobile user's JWT. Therefore:

- Never embed `API_BEARER_TOKEN` in a mobile application.
- Never trust an `X-User-ID` supplied directly by a mobile client.
- The ESS backend must validate the user's login/JWT and set `X-User-ID`.
- The device-reset token is restricted to an admin, support, or OTP recovery flow.

## 2. Base URLs

Local development:

```text
http://127.0.0.1:8000
```

Docker/Coolify container port:

```text
8080
```

Production example:

```text
https://face-api.example.com
```

Swagger/OpenAPI documentation (development/staging when `ENABLE_API_DOCS=true`):

```text
GET /docs
GET /openapi.json
```

## 3. Headers

Protected service request:

```http
Content-Type: application/json
Authorization: Bearer <API_BEARER_TOKEN>
```

User-scoped ESS request:

```http
Content-Type: application/json
Authorization: Bearer <API_BEARER_TOKEN>
X-User-ID: <authenticated-user-id>
```

Face enrollment, face status, and registered-face verification also require the
server-registered device identity:

```http
X-Device-ID: <stable-installation-device-id>
```

Device reset additionally requires:

```http
X-Device-Reset-Token: <DEVICE_RESET_TOKEN>
```

## 4. Application Workflow

```text
1. Validate client code
2. Log in through the external ESS backend
3. Register or verify the user's device
4. Check face-enrollment status
5. Register a face if no template exists
6. Verify a live face
7. Let the ESS backend record attendance or perform the protected action
```

Login and attendance persistence are not implemented by this Face API. They are
responsibilities of the existing ESS backend.

## 5. Step 1: Validate Client Code

### Request

```http
POST /api/public/clients/validate
```

This endpoint is public and is intended for use before login.

```json
{
  "code": "CLIENT001"
}
```

Validation rules:

- `code`: string, 1 to 64 characters
- Codes are trimmed and normalized to uppercase

### Valid response

HTTP `200`:

```json
{
  "valid": true,
  "client": {
    "id": "client-uuid",
    "code": "CLIENT001",
    "name": "Example Client"
  }
}
```

### Invalid or inactive response

HTTP `200`:

```json
{
  "valid": false,
  "client": null
}
```

Invalid codes intentionally do not return `404`. The app should check the
`valid` boolean.

## 6. Step 2: User Login

User login is not provided by this repository. The mobile app must call the
existing ESS authentication endpoint and receive a user session/JWT.

Conceptual response:

```json
{
  "access_token": "<user-jwt>",
  "user_id": "user-001"
}
```

The ESS backend validates this identity before forwarding user-scoped requests
to the Face API.

## 7. Step 3: Device Registration and Verification

The mobile app should generate one stable installation UUID and keep it in
secure platform storage.

### Register device

```http
POST /api/ess/device/register
```

```json
{
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "platform": "android",
  "public_key": null
}
```

Request types:

- `device_id`: string, 8 to 255 characters; letters, numbers, `.`, `_`, `:`, and `-`
- `platform`: `android`, `ios`, `web`, or `other`
- `public_key`: optional string, maximum 4096 characters

New registration returns HTTP `201`:

```json
{
  "registered": true,
  "device_id": "550e8400-e29b-41d4-a716-446655440000",
  "platform": "android",
  "registered_at": "2026-07-13T10:00:00+00:00",
  "already_registered": false
}
```

Registering the same device again is idempotent and returns
`"already_registered": true`. Registering a different device for the same user
returns HTTP `409` with code `user_device_conflict`.

### Verify device

```http
POST /api/ess/device/verify
```

```json
{
  "device_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Success, HTTP `200`:

```json
{
  "verified": true
}
```

A mismatched device returns HTTP `403` with code `device_not_authorized`. The
ESS backend must stop face verification and protected business actions after
this failure.

### Device status

```http
GET /api/ess/device/status
```

```json
{
  "registered": true,
  "device": {
    "device_id": "550e8400-e29b-41d4-a716-446655440000",
    "platform": "android",
    "registered_at": "2026-07-13T10:00:00+00:00",
    "last_verified_at": "2026-07-13T10:05:00+00:00"
  }
}
```

### Reset device

```http
POST /api/ess/device/reset
```

Optional body:

```json
{
  "reason": "User replaced the phone"
}
```

Success:

```json
{
  "reset": true
}
```

This endpoint requires `X-Device-Reset-Token` and must not be called directly
from a normal mobile session.

## 8. Step 4: Check Face-Enrollment Status

```http
GET /api/ess/face/status
```

Not enrolled:

```json
{
  "registered": false,
  "registered_at": null,
  "model": null
}
```

Enrolled:

```json
{
  "registered": true,
  "registered_at": "2026-07-13T10:10:00+00:00",
  "model": {
    "detector": "yunet_2023mar_opencv",
    "recognizer": "arcface_r100_onnx",
    "preprocessing": "align112_rgb_v1"
  }
}
```

The app should call face registration only when `registered` is `false`.

## 9. Step 5: Register Face

```http
POST /api/ess/face/register
```

Minimal request:

```json
{
  "image": {
    "kind": "base64_jpeg",
    "data": "<base64-image>"
  }
}
```

Full request:

```json
{
  "request_id": "register-001",
  "image": {
    "kind": "base64_jpeg",
    "data": "<base64-image>"
  },
  "face_selector": "largest",
  "quality_policy": {
    "reject_if_no_face": true,
    "reject_if_multiple_faces": true,
    "min_detection_confidence": 0.85
  }
}
```

Successful registration returns HTTP `201`:

```json
{
  "registered": true,
  "user_id": "user-001",
  "registered_at": "2026-07-13T10:10:00+00:00",
  "model": {
    "detector": "yunet_2023mar_opencv",
    "recognizer": "arcface_r100_onnx",
    "preprocessing": "align112_rgb_v1"
  }
}
```

The backend detects and aligns the face, extracts an embedding, encrypts the
template, and stores one template per user. It does not return the raw image or
embedding. A second enrollment returns HTTP `409` with code
`face_already_registered`.

## 10. Step 6: Verify Live Face

```http
POST /api/ess/face/verify
```

```json
{
  "request_id": "attendance-001",
  "image": {
    "kind": "base64_jpeg",
    "data": "<live-camera-base64>"
  }
}
```

Match response, HTTP `200`:

```json
{
  "verified": true,
  "decision": "match",
  "similarity_cosine": 0.72,
  "threshold": 0.267517
}
```

Non-match response, also HTTP `200`:

```json
{
  "verified": false,
  "decision": "non_match",
  "similarity_cosine": 0.15,
  "threshold": 0.267517
}
```

The app must use the backend's `verified` value. It must not hardcode or apply
its own similarity threshold.

## 11. Step 7: Record Attendance or Perform the Action

This repository does not provide an attendance-write endpoint. After successful
device and face verification, the ESS backend must record attendance or perform
the protected action server-side.

```text
device verified == true
AND face verified == true
THEN ESS backend records attendance/action
```

The mobile app must not be allowed to submit a self-declared `verified: true`
value as proof.

## 12. Image Request Types

Allowed image kinds:

```text
base64_jpeg
base64_png
```

Face selectors:

```text
largest
highest_confidence
face_index
all
```

Default quality policy:

```json
{
  "reject_if_no_face": true,
  "reject_if_multiple_faces": true,
  "min_detection_confidence": 0.85
}
```

## 13. Low-Level Face Engine Endpoints

These endpoints are primarily intended for trusted backend/service use:

```text
GET  /v1/models/current
POST /v1/faces/detect
POST /v1/faces/embed
POST /v1/faces/verify
```

`POST /v1/faces/verify` compares two images included in the same request.
`POST /api/ess/face/verify` compares one live image with the user's stored,
encrypted template.

## 14. Client Administration Endpoints

Protected service endpoints:

```text
POST /api/clients
GET  /api/clients
```

These endpoints are for backend/admin use, not the pre-login mobile flow.

## 15. Error Handling

Common status codes:

| Status | Meaning |
| --- | --- |
| `200` | Successful request; inspect `verified` or `valid` for business result |
| `201` | Face or device registered |
| `401` | Missing/invalid service authorization or user identity |
| `403` | Device mismatch or reset authorization failure |
| `404` | No registered face for the user |
| `409` | Face/device conflict or active model changed |
| `415` | Invalid Base64/image payload or unsupported image format |
| `422` | Invalid request fields, no face, multiple faces, or low-quality face |
| `429` | Public client-validation rate limit exceeded |
| `500` | Model, inference, encryption, or stored-template failure |
| `503` | Required calibration, encryption, or reset configuration is unavailable |

ESS domain errors normally use:

```json
{
  "detail": {
    "code": "device_not_authorized",
    "message": "This device is not authorized for the user"
  }
}
```

FastAPI request-validation errors use the standard `detail` array. Low-level
face-verification errors may use `detail.error.code`. Clients should check the
HTTP status first and then read either `detail.code` or `detail.error.code`.

## 16. Coolify Deployment Contract

Recommended application configuration:

```text
Build pack: Dockerfile
Branch: main
Container port: 8080
Liveness endpoint: /healthz
Container readiness/health check: /readyz
Persistent data path: /app/data
Model mount path: /app/models
```

Required production environment variables:

```env
ENVIRONMENT=production
API_BEARER_TOKEN=<strong-service-secret>
BIOMETRIC_ENCRYPTION_KEY=<persistent-fernet-key>
DEVICE_RESET_TOKEN=<admin-recovery-secret>
CORS_ALLOWED_ORIGINS=https://ess.example.com
ENABLE_API_DOCS=false
CLIENT_VALIDATION_RATE_LIMIT_PER_MINUTE=30

ESS_DATABASE_PATH=/app/data/ess.sqlite3
DETECTOR_PROVIDER=yunet
RECOGNIZER_PROVIDER=arcface_onnx
YUNET_MODEL_PATH=/app/models/face_detection_yunet_2023mar.onnx
ARCFACE_MODEL_PATH=/app/models/face-recognition-resnet100-arcface.onnx
CALIBRATION_DIR=/app/calibration
REQUIRE_CALIBRATION=true
USE_CALIBRATED_THRESHOLD=true
ONNX_PROVIDERS=CPUExecutionProvider
BACKEND_VERSION=phase-5
```

Do not set `MATCH_THRESHOLD` unless an explicit emergency override is required;
otherwise it overrides the model-specific calibration profile.

Operational requirements:

- Persist `/app/data`, or face and device registrations will be lost on redeploy.
- Back up `BIOMETRIC_ENCRYPTION_KEY`; changing or losing it makes existing
  templates unreadable.
- Upload/mount the ONNX model files because they are intentionally excluded from Git.
- Use a single application replica while SQLite is the persistence backend.
- Ensure mounted data/model paths are readable/writable by the non-root container user.
- Expose the service through HTTPS.
- Apply rate limiting to the public client-validation endpoint.

## 17. Integration Checklist

- [ ] Final production base URL configured in the app/gateway
- [ ] ESS login/JWT integration confirmed
- [ ] Service bearer token stored only on the backend
- [ ] Stable device ID stored securely on the device
- [ ] Gateway forwards the same device ID as `X-Device-ID` on face endpoints
- [ ] Device conflict and reset UX implemented
- [ ] Camera image converted to JPEG/PNG Base64
- [ ] Face-quality errors mapped to user-friendly messages
- [ ] App uses `valid` and `verified` booleans, not custom thresholds
- [ ] Attendance/action is recorded only by the ESS backend
- [ ] Coolify model and data volumes configured
- [ ] Secrets backed up and excluded from source control
