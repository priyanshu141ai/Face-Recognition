# ESS Gateway signed-claim contract

## Trust boundary

```text
Mobile app -> authenticated ESS Gateway -> Face API
              signs ES256 assertion       verifies public JWKS
```

The ESS Gateway owns the service bearer and a P-256 signing key. The Face API receives only a public JWKS. The mobile app never calls protected Face API routes directly, and the gateway private key must never enter Git, Docker images, Face API variables, logs, or backups.

Production and staging require both headers:

```http
Authorization: Bearer <gateway-service-secret>
X-Gateway-Assertion: <short-lived-ES256-JWS>
X-Request-ID: <opaque-request-id>
```

`X-User-ID` and `X-Device-ID` are compatibility headers only. Signed claims are authoritative; if a compatibility header is sent, it must match the assertion. Unsigned identity headers are rejected in staging and production.

## Required protected claims

The JOSE header must contain `alg=ES256` and a trusted `kid`. Required payload claims are:

```json
{
  "iss": "https://<ess-gateway>",
  "aud": "<face-api-audience>",
  "sub": "<user-id>",
  "iat": 0,
  "nbf": 0,
  "exp": 0,
  "jti": "<unique-one-time-id>",
  "tenant_id": "<validated-tenant>",
  "user_id": "<validated-user>",
  "device_id": "<candidate-or-registered-device>",
  "device_key_version": 1,
  "session_id": "<authenticated-session>",
  "action": "face_verify",
  "request_id": "<same-as-X-Request-ID>",
  "http_method": "POST",
  "request_path": "/api/ess/face/verify",
  "gateway_version": "<gateway-release>"
}
```

Rules:

- `sub` must equal `user_id`.
- Issuer, audience, signature, key ID, times, and maximum lifetime are verified.
- Maximum lifetime is 90 seconds by default and never more than 120 seconds in hardened environments.
- `jti` is one-time; the Face API stores only its hash and rejects replay.
- Method, exact path, request ID, action, user, device, and key version are request-bound.
- Active-device routes reject missing, revoked, changed, or stale-key devices.

## Action mapping

| Endpoint | `action` | Active device |
| --- | --- | --- |
| `POST /api/clients` | `client_create` | No |
| `GET /api/clients` | `client_list` | No |
| `GET /v1/models/current` | `models_current` | No |
| `POST /api/ess/device/challenge` | `device_challenge:<operation>` | Non-register checked |
| `POST /api/ess/device/register` | `device_register` | Bootstrap; key version `0` |
| `GET /api/ess/device/status` | `device_status` | Candidate login check |
| `POST /api/ess/device/verify` | `device_verify` | Yes |
| `POST /api/ess/device/rotate` | `device_rotate` | Yes |
| `POST /api/ess/device/revoke` | `device_revoke` | Yes |
| `POST /api/ess/device/reset` | `device_reset` | Recovery flow |
| `POST /api/ess/liveness/challenge` | `liveness_challenge` | Yes |
| `POST /api/ess/face/register` | `face_register` | Yes |
| `GET /api/ess/face/status` | `face_status` | Yes |
| `POST /api/ess/face/verify` | `face_verify` | Yes |
| `POST /api/ess/face/revoke` | `face_revoke` | Yes |
| `POST /api/ess/face/delete` | `face_delete` | Yes |
| `POST /v1/faces/verify` | `face_engine_verify` | Yes |
| `POST /v1/faces/detect` | `face_engine_detect` | Yes |
| `POST /v1/faces/embed` | `face_engine_embed` | Yes |

Public `/`, `/healthz`, `/readyz`, and `/api/public/clients/validate` remain public.

## Responsibility split

- Mobile: secure device key, challenge signature, capture, GPS, and Google/Apple token collection.
- ESS Gateway: user/tenant authorization, provider attestation verification, office-radius/shift/attendance rules, assertion signing, session invalidation, and attendance write.
- Face API: service/assertion/device/attestation checks, face/liveness decision, replay prevention, and privacy-safe audit outcome.

A gateway assertion cannot turn an app Boolean into trusted liveness. The selected provider result must be independently verified through its official server mechanism and separately replay-bound as described in `docs/real_liveness_integration.md`.

The Face API never calculates office radius and never accepts a client-declared attendance result. Optional location/attendance references are trace bindings only.

## Key rotation and errors

Publish old and new public keys together under different `kid` values. Start signing with the new key, wait beyond the assertion/replay window, then remove the old public key. Private JWK material, unknown/duplicate `kid`, `alg=none`, symmetric algorithms, and algorithm substitution are rejected.

The service bearer currently has one active value. Rotate it in the secret manager with a coordinated gateway/API restart, revoke the old value immediately after the cutover, and isolate ingress during an emergency leak. There is no indefinite previous-token fallback.

| Code | Meaning |
| --- | --- |
| `gateway_assertion_missing` | Protected request did not include the assertion |
| `gateway_assertion_invalid` | Malformed, bad signature, missing claim, or unsupported token |
| `gateway_assertion_expired` / `gateway_assertion_not_yet_valid` | Assertion time window failed |
| `gateway_issuer_invalid` / `gateway_audience_invalid` | Trust destination failed |
| `gateway_key_unknown` | `kid` is not in the mounted public JWKS |
| `gateway_action_mismatch` / `gateway_request_mismatch` | Action, method, path, or request ID differs |
| `gateway_user_mismatch` / `gateway_device_mismatch` | Compatibility/body identity differs from signed claims |
| `gateway_tenant_mismatch` | Tenant is not in the configured allowlist |
| `gateway_assertion_replayed` | Hashed `jti` was already consumed |
| `device_not_registered` / `device_revoked` | Active-device policy failed |
| `device_key_version_mismatch` | Assertion used a stale/wrong device key version |
| `device_attestation_required` / `device_attestation_stale` / `device_attestation_rejected` | Attestation policy failed |

Never log or return the assertion, signature, key coordinates, image, Base64 payload, or embedding.

Staging requires assertions but may explicitly defer real attestation/liveness. Production additionally requires recent attestation, real liveness, field-approved calibration, private dependencies, backups, monitoring, and gateway-only ingress.
