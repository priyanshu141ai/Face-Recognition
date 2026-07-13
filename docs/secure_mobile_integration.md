# Secure mobile integration

## Required architecture

```text
Mobile App --user session--> ESS Gateway --service bearer + ES256 assertion--> Face API
```

The app never receives the Face API bearer, database credentials, biometric key, reset token, model paths, or backend/provider secrets. The app creates a non-exportable P-256 key and sends only its public key through ESS.

Real anti-spoof integration is currently blocked until an approved provider is selected. The current multi-frame/mock/generic assertion paths are not production liveness. Follow `docs/liveness_provider_selection.md` before implementing a mobile SDK.

## Sequence

1. ESS authenticates the user and validates client tenancy.
2. Android generates ECDSA P-256 in Android Keystore; iOS generates/stores P-256 using Secure Enclave/Keychain APIs supported by the target OS.
3. ESS requests `POST /api/ess/device/challenge` with operation `register`.
4. App signs the returned `canonical_payload` exact UTF-8 bytes with ECDSA-SHA256 and returns standard Base64 DER signature plus the PEM SubjectPublicKeyInfo.
5. ESS registers the device. For later sensitive operations, it repeats challenge/signature with the exact operation.
6. ESS requests a device proof for `liveness_challenge`, then calls `POST /api/ess/liveness/challenge` with `intended_action`.
7. The app captures ordered frames after issuance and returns them to ESS. Production UI should not offer gallery selection, but the backend cannot trust an app-supplied “camera only” claim by itself.
8. A selected approved SDK/service evaluates liveness and ESS verifies the official server result; mobile never creates the trusted assertion.
9. For enrollment, ESS sends exactly three separate template captures (`front`, slight `left`, slight `right`) plus liveness evidence. For verification, it sends only one live probe/liveness session.
10. ESS obtains a separate device proof for `face_register`/`face_verify`, then calls the Face API with liveness evidence.
11. Face API verifies bearer, signed gateway claims, active device/key version, P-256 proof, replay, liveness, and face match.
12. ESS records attendance server-side only after HTTP 200 with `verified:true`. The app must not decide attendance from a local Boolean.

## Headers

```http
Authorization: Bearer <gateway-owned-service-token>
Content-Type: application/json
X-User-ID: <ESS-authenticated-user-id>
X-Device-ID: <registered-installation-id>
X-Request-ID: <trace-id>
X-Gateway-Assertion: <short-lived-ES256-JWS>
```

The signed assertion is authoritative. Compatibility identity headers may be omitted; if retained, they must match it. Exact claims/actions are in `docs/gateway_signed_claims.md`.

## Face verification request shape

```json
{
  "request_id":"attendance-opaque-id",
  "device_proof":{"challenge_id":"<uuid>","nonce":"<nonce>","signature":"<base64-der>"},
  "liveness":{
    "challenge_id":"<uuid>",
    "challenge_nonce":"<nonce>",
    "capture_timestamp":"<RFC3339 UTC>",
    "challenge_action":"<returned-action>",
    "frames":[{"kind":"base64_jpeg","data":"<omitted>"}],
    "provider_assertion":"<trusted-provider-assertion>"
  }
}
```

Success is `{"verified":true,"decision":"match","similarity_cosine":...,"threshold":...}`. A non-match is normal HTTP 200 with `verified:false`. Never hardcode a threshold or call the similarity/percentage an identity probability.

## Three-angle enrollment request shape

```json
{
  "request_id":"enrollment-opaque-id",
  "enrollment_images":[
    {"angle":"front","image":{"kind":"base64_jpeg","data":"<omitted>"}},
    {"angle":"left","image":{"kind":"base64_jpeg","data":"<omitted>"}},
    {"angle":"right","image":{"kind":"base64_jpeg","data":"<omitted>"}}
  ],
  "device_proof":{"challenge_id":"<uuid>","nonce":"<nonce>","signature":"<base64-der>"},
  "liveness":{"challenge_id":"<uuid>","challenge_nonce":"<nonce>","capture_timestamp":"<RFC3339 UTC>","challenge_action":"<returned-action>","frames":[{"kind":"base64_jpeg","data":"<omitted>"}],"provider_assertion":"<trusted-provider-assertion>"}
}
```

The API requires exactly one front, slight-left, and slight-right capture. These
template inputs are separate from liveness frames. It independently validates
each capture, L2-normalizes each embedding, checks pairwise identity consistency
with the active calibrated/configurable match threshold, arithmetic-means the
accepted vectors, and L2-normalizes the final template. Only that encrypted fused
template and safe metadata are stored. No accuracy improvement is assumed until
representative deployment validation is complete.

## Errors, timeout, and retry

| Status/code | App behavior |
| --- | --- |
| 401 authentication/device proof | Re-authenticate or repeat a fresh device challenge; do not reuse nonce |
| 403 liveness/signature/device | Stop the attempt and show a safe recapture/support message |
| 409 challenge/replay/conflict | Obtain a completely new challenge and capture |
| 415/422 capture quality | Recapture with actionable lighting/face guidance |
| 429 rate/cooldown | Honor `Retry-After`; do not loop |
| 503 unavailable | Retry with bounded exponential backoff; never mark attendance locally |

Use a server-measured timeout budget; start with 30 seconds for capture verification and 5–10 seconds for metadata/challenge calls. Do not automatically retry signatures, frames, or attendance writes; acquire fresh challenges and use idempotent ESS transaction IDs.
