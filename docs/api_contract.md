# API Contract

This file is the main contract reference for the frontend and mobile client. Keep it updated whenever request or response fields change.

## Health endpoints
- GET /healthz
  - Response: {"status": "ok"}
- GET /readyz
  - Response: {"status": "ready", "models_loaded": true, "provider": "mock", "version": "phase-4.1"}

## Face verification
- POST /v1/faces/verify
- Request fields:
  - request_id: optional string
  - image_a: base64 JPEG/PNG payload
  - image_b: base64 JPEG/PNG payload
  - face_selector: "largest", "highest_confidence", "face_index", or "all"
  - face_index: optional integer when face_selector is "face_index"
  - return_embeddings: boolean
  - quality_policy: reject_if_no_face, reject_if_multiple_faces, min_detection_confidence
- Response fields:
  - decision
  - match_score_percent
  - similarity_cosine
  - threshold
  - model_versions
  - faces
  - timings_ms

## Model metadata
- GET /v1/models/current
- Returns the current detector, recognizer, preprocessing, threshold, and calibration versions.

## Face detection
- POST /v1/faces/detect
- Request fields:
  - request_id: optional string
  - image: base64 JPEG/PNG payload
  - quality_policy: reject_if_no_face, reject_if_multiple_faces, min_detection_confidence
- Response fields:
  - request_id
  - faces

## ESS integration endpoints

Protected endpoints use the configured bearer token. User-scoped endpoints also
require `X-User-ID`, which must be set by a trusted authenticated gateway and not
accepted directly from an untrusted client.

### Client codes

- `POST /api/clients` creates an active/inactive client code (protected).
- `GET /api/clients` lists client codes (protected).
- `POST /api/public/clients/validate` validates a code before login (public).
  - Request: `{"code": "ACME-01"}`
  - Valid response: `{"valid": true, "client": {"id": "...", "code": "ACME-01", "name": "Acme"}}`
  - Invalid and inactive codes both return `{"valid": false, "client": null}`.

### Face enrollment

- `POST /api/ess/face/register` registers exactly one encrypted face template per user.
- `GET /api/ess/face/status` reports whether the authenticated user is enrolled.
- `POST /api/ess/face/verify` compares a live image with the enrolled template.
- Registration returns `409 face_already_registered` instead of silently replacing a biometric template.
- `BIOMETRIC_ENCRYPTION_KEY` must be configured with a Fernet key. Embeddings are never returned by these endpoints.

The register and verify request body uses the same `image`, `face_selector`,
`face_index`, and `quality_policy` fields as the face embedding endpoint.

### One-user-one-device binding

- `POST /api/ess/device/register` accepts `device_id`, `platform`, and optional `public_key`.
- `POST /api/ess/device/verify` accepts `device_id` and returns `{"verified": true}` or HTTP 403.
- `GET /api/ess/device/status` returns the current binding.
- `POST /api/ess/device/reset` removes the binding and requires `X-Device-Reset-Token`.

Registration is atomic. A user cannot register a second device until reset, and
one device ID cannot be assigned to two users. `DEVICE_RESET_TOKEN` is a
backend/admin recovery secret and must never be included in a mobile build.

## Notes for contributors
- Keep response field names stable unless the client contract is intentionally changed.
- Do not expose raw images, base64 payloads, or embeddings in logs.
- When adding new fields, update both this file and the related Pydantic schema.
