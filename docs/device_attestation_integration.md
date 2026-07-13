# Device attestation integration

Google Play Integrity and Apple App Attest verification happens in the ESS Gateway or another trusted verifier. The Face API does not call Google/Apple directly and never trusts a raw mobile Boolean.

After provider verification, the gateway may sign this claim:

```json
{
  "device_attestation": {
    "provider": "play_integrity",
    "verdict": "MEETS_DEVICE_INTEGRITY",
    "checked_at": 0,
    "app_identifier": "<allowlisted-package-or-bundle-id>",
    "platform": "android"
  }
}
```

Supported provider/platform pairs are `play_integrity/android` and `app_attest/ios`. The Face API checks provider, verdict, app identifier, platform match, timestamp freshness, and future-clock limits. Production requires a recent attestation; staging may defer it explicitly.

Attestation is a risk signal, not proof of a live face and not a replacement for P-256 possession proof. On failure, deny the operation and record only safe outcome codes.
