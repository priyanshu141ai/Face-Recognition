# Latest App API Contract

Status: authoritative repository contract as of 2026-07-13. Older enrollment
examples that use one `image` are deprecated for registration.

## Trust boundary

```text
Mobile app -> authenticated ESS Gateway -> private Face API
```

The mobile app must not call protected Face API routes directly. The ESS Gateway
owns the service bearer and short-lived ES256 assertion. Signed gateway claims
are authoritative; compatibility `X-User-ID`/`X-Device-ID` headers must match.
The mobile app never receives service, reset, database, biometric, provider, or
gateway-signing secrets.

Protected gateway requests use:

```http
Authorization: Bearer <gateway-owned>
X-Gateway-Assertion: <short-lived ES256 assertion>
X-Request-ID: <same request ID signed by gateway>
Content-Type: application/json
```

Sensitive device/face operations additionally require a fresh P-256 device
challenge proof. Secure enrollment and verification require liveness evidence.
No validated real liveness provider is selected yet, so production attendance
remains blocked.

## App workflow

```text
validate client -> ESS login -> device challenge/register/verify
-> face status -> three-angle enrollment if allowed
-> one-probe liveness + face verify -> ESS writes attendance server-side
```

## Three-angle face registration

`POST /api/ess/face/register` returns HTTP `201` on success.

```json
{
  "request_id": "enrollment-001",
  "enrollment_images": [
    {"angle":"front","image":{"kind":"base64_jpeg","data":"<omitted>"}},
    {"angle":"left","image":{"kind":"base64_jpeg","data":"<omitted>"}},
    {"angle":"right","image":{"kind":"base64_jpeg","data":"<omitted>"}}
  ],
  "face_selector": "largest",
  "quality_policy": {
    "reject_if_no_face": true,
    "reject_if_multiple_faces": true,
    "min_detection_confidence": 0.85
  },
  "device_proof": {
    "challenge_id": "<uuid>",
    "nonce": "<server nonce>",
    "signature": "<base64 DER signature>"
  },
  "liveness": {
    "challenge_id": "<uuid>",
    "challenge_nonce": "<server nonce>",
    "capture_timestamp": "<RFC3339 UTC>",
    "challenge_action": "<returned action>",
    "frames": [{"kind":"base64_jpeg","data":"<omitted>"}],
    "provider_assertion": "<server-verified provider result>"
  },
  "consent_reference": "<opaque reference>"
}
```

Exactly one `front`, slight-`left`, and slight-`right` capture is required.
Enrollment images create the template. Liveness frames prove live presence and
are not enrollment inputs. Each enrollment image is independently decoded,
size/pixel checked, detected, quality checked, aligned, embedded, and normalized.
Accepted embeddings use normalize-each -> arithmetic mean -> normalize-final.

```json
{
  "registered": true,
  "status": "registered",
  "user_id": "user-001",
  "capture_count": 3,
  "captured_angles": ["front", "left", "right"],
  "template_version": "three_angle_mean_l2_v1",
  "registered_at": "<RFC3339 UTC>",
  "model": {
    "detector": "yunet_2023mar_opencv",
    "recognizer": "arcface_r100_onnx",
    "preprocessing": "align112_rgb_v1"
  }
}
```

The API stores only the encrypted fused template and safe metadata. It never
returns or intentionally persists images, Base64, or embeddings. Re-registering
an active template returns `409 face_already_registered`. Single-image
registration is rejected even when development legacy verification is enabled.

## Face status

`GET /api/ess/face/status` returns HTTP `200`.

Not registered:

```json
{"registered":false,"status":"not_registered","capture_count":0,"captured_angles":[],"template_version":null,"registered_at":null,"model":null}
```

Registered returns the same safe template fields as registration. Revoked:

```json
{"registered":false,"status":"revoked","capture_count":3,"captured_angles":["front","left","right"],"template_version":"three_angle_mean_l2_v1","registered_at":"<RFC3339 UTC>","model":null}
```

## One-probe face verification

`POST /api/ess/face/verify` still uses one live probe/liveness session. It does
not require three attendance photos. In secure mode, liveness/provider frames
are evaluated first; the selected probe is compared with the stored encrypted
template only after gateway, device-proof, replay, and liveness checks pass.

```json
{
  "request_id": "attendance-001",
  "device_proof": {"challenge_id":"<uuid>","nonce":"<nonce>","signature":"<base64 DER>"},
  "liveness": {
    "challenge_id":"<uuid>",
    "challenge_nonce":"<nonce>",
    "capture_timestamp":"<RFC3339 UTC>",
    "challenge_action":"<returned action>",
    "frames":[{"kind":"base64_jpeg","data":"<omitted>"}],
    "provider_assertion":"<server-verified provider result>"
  }
}
```

Match and normal non-match both return HTTP `200`:

```json
{"verified":true,"decision":"match","similarity_cosine":0.72,"threshold":0.267517}
```

```json
{"verified":false,"decision":"non_match","similarity_cosine":0.15,"threshold":0.267517}
```

The app uses `verified`; it must not calculate a decision, hardcode the
threshold, or present cosine similarity as identity probability.

## Error handling

Common registration errors:

| HTTP | Code | App action |
| --- | --- | --- |
| 401 | bearer/assertion/device proof missing or invalid | re-authenticate; obtain fresh proof |
| 403 | gateway/device/liveness scope or policy rejection | stop; do not fall back |
| 409 | replay, reused challenge, active enrollment | obtain fresh challenge or use lifecycle flow |
| 415 | `invalid_image_payload` | recapture/compress a supported image |
| 422 | `invalid_enrollment_angles` | send exactly front/left/right |
| 422 | `duplicate_enrollment_angle` | send each angle once |
| 422 | `no_face_detected` | recapture the named angle |
| 422 | `multiple_faces_detected` | recapture with one face |
| 422 | `face_quality_rejected` | improve capture conditions |
| 422 | `enrollment_identity_mismatch` | restart enrollment with the same person |
| 429 | `rate_limited` | honor `Retry-After` |
| 503 | dependency/provider unavailable | fail closed; bounded retry |

Security-domain errors use `detail.code`, `detail.message`, and optional
`detail.retry_after_seconds`. Some route errors use the same `detail.code` and
`detail.message` without retry metadata. The app must never show internal
assertion/provider details.

## Payload and timeout limits

Supported kinds are `base64_jpeg` and `base64_png`. Each image is limited by
`MAX_IMAGE_MB` after Base64 size preflight and by `MAX_IMAGE_PIXELS` before model
processing. Base64 adds about one-third transport overhead, and enrollment may
also include liveness frames. The reverse proxy must enforce a measured finite
total request-body limit because application parsing still allocates the JSON
body. Controlled staging may keep Base64 JSON; multipart is a future versioned
contract decision, not an automatic change.

Start with a 30-second face-operation timeout and measure staging p95. Metadata
calls may use 5–10 seconds. Never automatically replay a challenge, assertion,
signature, provider result, or attendance write.

## Current blockers

- No selected/validated real liveness provider or spoof evaluation.
- No approved fused-template workforce calibration/fairness validation.
- No live Coolify deployment, gateway/mobile E2E, or backup/restore evidence.
- Gateway assertion binds request ID/method/path/action/user/device, but not a
  canonical request-body digest; body-digest design requires a versioned ESS/mobile contract.
