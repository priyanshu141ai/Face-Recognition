# Real liveness integration contract

Status: **BLOCKED pending provider selection**. This is a provider-neutral contract, not a claim that real liveness exists.

## Target trust flow

```text
Mobile approved capture SDK
  -> ESS-authenticated session + device proof + platform attestation
  -> Face API server challenge
  -> provider session/capture
  -> provider server verification
  -> trusted provider result bound by ESS Gateway assertion
  -> Face API provider-result verification + replay consumption
  -> face comparison
  -> ESS atomic attendance decision
```

The mobile app may transport a provider reference/token but cannot produce the trusted decision. Gallery blocking is UX only. Blink, head-turn, frame difference, and single-use challenges are replay controls, not sufficient presentation-attack detection.

## Future normalized provider result

The selected adapter should normalize only verified data:

```text
provider, provider_request_id, provider_session_id, capture_session_id,
challenge_id, tenant_id, user_id, device_id, device_key_version,
gateway_request_id, intended_action, issued_at, evaluated_at, expires_at,
decision(pass/reject/indeterminate), reason_code, confidence_category,
provider_key_id, assertion_hash, sandbox
```

A numeric score is included only when official documentation defines its meaning and operating policy. Raw provider payloads, assertions, media, and secrets are excluded from normal responses, logs, and storage.

## Required verification

- official signature/webhook/result-lookup mechanism;
- explicit allowed algorithm, trusted `kid`, issuer, audience, time checks, and maximum age;
- exact local challenge/provider session/request/user/device/action binding;
- current active device and key version;
- allowed provider and production/sandbox mode;
- pass decision; reject and indeterminate never become verified;
- atomic single-use claim for challenge, assertion/result, capture/session, and frame hashes;
- safe 503 for provider unavailable/timeout/not configured;
- no automatic duplicate charged session on request retry.

Suggested safe errors include `liveness_provider_not_configured`, `liveness_provider_unavailable`, `liveness_provider_timeout`, `liveness_assertion_invalid`, `liveness_assertion_expired`, `liveness_assertion_replayed`, `liveness_challenge_invalid`, `liveness_challenge_expired`, `liveness_challenge_reused`, `liveness_user_mismatch`, `liveness_device_mismatch`, `liveness_action_mismatch`, `liveness_rejected`, and `liveness_indeterminate`.

## Challenge gaps to close after selection

The current local challenge already has a random nonce, user/device/action, type, capture count, timestamps, attempt count, single-use consumption, and frame replay hashes. A real-provider revision must additionally bind tenant, device-key version, gateway request ID, provider/mode, provider session ID, and selected capture protocol. The database migration must be designed from the official provider contract rather than guessed now.

## Enrollment and verification

When production liveness is required, both enrollment and registered-face verification require all security layers. `verified=true` is allowed only when gateway, active device/key, P-256 proof, recent platform attestation, real provider liveness, replay controls, and face comparison all pass.

Future business response should separate controls without provider internals:

```json
{"verified":true,"decision":"match","liveness":"accepted","similarity_cosine":0.72,"threshold":0.267517}
```

Similarity is not identity probability. Enrollment uses a distinct challenge/assertion from verification. Replayed results, revoked devices, cross-action results, and unauthorized re-enrollment fail closed.

## Responsibility boundary

- Mobile: approved SDK capture, provider session reference, device challenge signature, Play Integrity/App Attest token, safe UI.
- ESS: authenticate/authorize, verify platform attestation, create/retrieve provider session/result where required, sign gateway assertion, enforce radius/shift rules, atomically write attendance.
- Face API: verify gateway and provider results, consume challenge/replay claims, run face match, return final secure result.

The Face API does not calculate location radius or store attendance.

## Outage and privacy

Provider outage, timeout, indeterminate result, or missing keys must deny attendance/enrollment with safe 503/403 behavior and bounded user retry. No face-only fallback is allowed. Raw frames are processed transiently by the Face API today and are not intentionally stored; provider retention/deletion and regional transfer must be approved before integration.
