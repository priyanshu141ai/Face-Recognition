# API Authentication

## Trust Model

The Face API uses a shared backend-to-backend bearer token. It does not validate
mobile-user JWTs directly.

Recommended production flow:

```text
Mobile App --user JWT--> ESS Backend/Gateway
ESS Backend --service bearer + trusted identity headers--> Face API
```

Never place `API_BEARER_TOKEN` or `DEVICE_RESET_TOKEN` in a mobile application.

## Development

Authentication may be disabled only in local development:

```env
ENVIRONMENT=development
API_BEARER_TOKEN=
```

## Production

Production startup fails if required secrets are missing, mock providers are
active, or wildcard CORS is configured.

```env
ENVIRONMENT=production
API_BEARER_TOKEN=<strong-service-secret>
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
POST /api/ess/device/verify
GET  /api/ess/device/status
POST /api/ess/device/reset
GET  /api/ess/face/status
POST /api/ess/face/register
POST /api/ess/face/verify
```

The low-level `/v1/faces/*` routes are for trusted backend/service use. Mobile
clients should use the ESS gateway workflow.

## Operational Requirements

- Rotate service and reset tokens through a controlled secret-management process.
- Back up the biometric encryption key; losing it makes stored templates unreadable.
- Keep Face API network access restricted to the ESS gateway where possible.
- Use HTTPS only.
- Rate-limit public endpoints at both the application and edge/gateway layers.
- Audit device resets, enrollment, verification, and attendance decisions in the ESS backend.
