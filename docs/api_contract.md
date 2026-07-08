# API Contract

This file is the main contract reference for the frontend and mobile client. Keep it updated whenever request or response fields change.

## Health endpoints
- GET /healthz
  - Response: {"status": "ok"}
- GET /readyz
  - Response: {"status": "ready", "models_loaded": true, "provider": "mock", "version": "phase-1"}

## Face verification
- POST /v1/faces/verify
- Request fields:
  - request_id: optional string
  - image_a: base64 JPEG/PNG payload
  - image_b: base64 JPEG/PNG payload
  - face_selector: currently only "largest"
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

## Notes for contributors
- Keep response field names stable unless the client contract is intentionally changed.
- Do not expose raw images, base64 payloads, or embeddings in logs.
- When adding new fields, update both this file and the related Pydantic schema.
