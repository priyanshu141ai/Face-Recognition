# Liveness and replay protection

## What is implemented

- Server-generated, short-lived, single-use challenges bound to user, device, and `face_register` or `face_verify`.
- Secure random nonce stored only as a SHA-256 hash.
- Capture timestamp, action, required frame count, expiry, attempt count, and scope validation.
- Short-lived exact frame-set replay detection without permanent image storage.
- A provider interface with `disabled`, test-only `mock`, and `external_assertion` adapters.

Replay protection is implemented, but production-grade anti-spoofing is not complete until a validated real liveness provider and representative spoof evaluation are configured. Head-turn/multi-frame prompts alone do not prove that a real live person is present.

Current Phase 4 status is **WAITING FOR PROVIDER SELECTION**. See [provider selection](liveness_provider_selection.md), [future real-provider contract](real_liveness_integration.md), and [spoof-validation protocol](liveness_spoof_validation_protocol.md).

## Flow

1. Obtain and sign a device challenge for operation `liveness_challenge`.
2. Call `POST /api/ess/liveness/challenge` with `{"intended_action":"face_verify","device_proof":{...}}`.
3. Capture the required ordered frames after challenge issuance.
4. Call face registration/verification with `liveness.challenge_id`, nonce, returned challenge type, current timestamp, frames, a provider assertion, and a separate device proof for the face operation.

The challenge is consumed only after provider approval. Expired, reused, cross-user, cross-device, wrong-action, stale-timestamp, insufficient-frame, and duplicate-capture requests fail closed.

## Provider adapter

`external_assertion` verifies generic server-side HMAC plumbing. It does not run anti-spoof inference, identify an approved vendor, prove official server verification, rotate provider keys, or supply spoof-test evidence. It must not be treated as completed production liveness. The assertion is `base64url(JSON).base64url(HMAC-SHA256(encoded_JSON))`; the JSON binds `challenge_id`, `user_id`, `device_id`, `challenge_type`, normalized `capture_timestamp`, and `approved`. `LIVENESS_ASSERTION_SECRET` stays between trusted backend services and is never shipped to the app.

`disabled` never approves. `mock` only checks test frame count and is rejected in production.
