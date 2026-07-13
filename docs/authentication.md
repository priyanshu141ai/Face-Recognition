# API Authentication

## Trust Model

The Face API requires a shared backend bearer plus a short-lived ES256 gateway assertion. It does not validate mobile-user JWTs directly.

Recommended production flow:

```text
Mobile App --user JWT--> ESS Backend/Gateway
ESS Backend --service bearer + signed gateway assertion--> Face API
```

Never place `API_BEARER_TOKEN` or `DEVICE_RESET_TOKEN` in a mobile application.
The assertion is authoritative; raw identity headers are development-only compatibility inputs. See [gateway signed claims](gateway_signed_claims.md).

## Development

Authentication may be disabled only in local development:

```env
ENVIRONMENT=development
API_BEARER_TOKEN=
```

## Production

Production startup also fails for insecure liveness/device legacy modes, unsafe
database/rate-limit configuration, automatic schema creation, and missing required
deployment calibration approval. See `docs/production_security.md`.

```env
ENVIRONMENT=production
API_BEARER_TOKEN=<strong-service-secret>
GATEWAY_ASSERTION_REQUIRED=true
ALLOW_UNSIGNED_IDENTITY_HEADERS=false
GATEWAY_ASSERTION_ISSUER=https://ess.example.com
GATEWAY_ASSERTION_AUDIENCE=face-api
GATEWAY_JWKS_PATH=/run/secrets/gateway-public.jwks.json
BIOMETRIC_ENCRYPTION_KEY=<persistent-fernet-key>
DEVICE_RESET_TOKEN=<admin-recovery-secret>
CORS_ALLOWED_ORIGINS=https://ess.example.com
ENABLE_API_DOCS=false
DETECTOR_PROVIDER=yunet
RECOGNIZER_PROVIDER=arcface_onnx
```

## Headers

Protected service endpoint:

```http
Authorization: Bearer <API_BEARER_TOKEN>
```

User-scoped ESS endpoint:

```http
Authorization: Bearer <API_BEARER_TOKEN>
X-User-ID: <authenticated-user-id>
```

Face enrollment/status/verification additionally requires:

```http
X-Device-ID: <registered-device-id>
```

Device reset additionally requires:

```http
X-Device-Reset-Token: <DEVICE_RESET_TOKEN>
```

## Endpoint Groups

Public:

```text
GET  /
GET  /healthz
GET  /readyz
POST /api/public/clients/validate
```

Service protected:

```text
GET  /v1/models/current
POST /v1/faces/detect
POST /v1/faces/embed
POST /v1/faces/verify
GET  /api/clients
POST /api/clients
```

User and device protected:

```text
POST /api/ess/device/register
POST /api/ess/device/challenge
POST /api/ess/device/verify
POST /api/ess/device/rotate
POST /api/ess/device/revoke
GET  /api/ess/device/status
POST /api/ess/device/reset
POST /api/ess/liveness/challenge
GET  /api/ess/face/status
POST /api/ess/face/register
POST /api/ess/face/verify
POST /api/ess/face/revoke
POST /api/ess/face/delete
```

The low-level `/v1/faces/*` routes are for trusted backend/service use. Mobile
clients should use the ESS gateway workflow.

## Operational Requirements

- Rotate service and reset tokens through a controlled secret-management process.
- Back up the biometric encryption key; losing it makes stored templates unreadable.
- Keep Face API network access restricted to the ESS gateway where possible.
- Use HTTPS only.
- Rate-limit public endpoints at both the application and edge/gateway layers.
- Require P-256 device proof and approved liveness for sensitive production calls.
- Audit device resets, enrollment, verification, and attendance decisions in the ESS backend.
- Rotate the single active bearer through the secret manager using a coordinated gateway/API cutover; remove the previous value immediately. JWKS rotation supports an intentionally short overlap of old/new public keys by `kid`.
