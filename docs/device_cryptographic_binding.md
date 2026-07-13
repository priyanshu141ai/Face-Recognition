# Cryptographic device binding

The device generates ECDSA P-256 (`secp256r1`) key material in Android Keystore or iOS secure storage. The private key is non-exportable and never sent to this backend. Registration sends PEM SubjectPublicKeyInfo only.

## Challenge and signature

Call `POST /api/ess/device/challenge` with the device ID and operation. For bootstrap registration, `operation=register` is allowed before binding; other operations require an active binding.

The response includes `canonical_payload`. Sign its exact UTF-8 bytes using ECDSA with SHA-256 and send the resulting ASN.1 DER signature as standard Base64. The canonical JSON is compact, ASCII, sorted by key, and contains:

```text
challenge_id, device_id, expires_at, issued_at, nonce, operation, user_id, version
```

The server validates key type, P-256 curve, PEM size, signature, nonce hash, scope, expiry, and single use. A copied device ID without the private key fails.

## Lifecycle

- `POST /api/ess/device/rotate`: signed by the current key; stores the new public key and increments `key_version`.
- `POST /api/ess/device/revoke`: signed by the current key; revoked devices cannot request normal challenges.
- `POST /api/ess/device/reset`: emergency/admin bearer plus reset token; use only behind an audited recovery workflow.
- Re-registration after revoke creates a new key version. Old keys cannot authenticate after rotation/re-registration.

Never put a sample private key, Face API bearer, reset token, or database credential in mobile code or documentation.
