# One-user/one-device login contract

The ESS Gateway authenticates the user first, creates a signed candidate-device assertion, and calls `GET /api/ess/device/status` with action `device_status`.

| `session_state` | Meaning | ESS/mobile action |
| --- | --- | --- |
| `registration_required` | No active device | Run P-256 registration |
| `active` | Device and key version match | Continue |
| `device_change_required` | Another device is registered | Stop; use approved recovery |
| `key_refresh_required` | Assertion key version is stale | Refresh session/assertion |

The Face API never silently replaces a device. Registration requires a fresh server challenge and proof from a non-exportable P-256 key. Sensitive calls require gateway assertion, active device/key-version match, and endpoint-specific device proof.

Approved replacement:

1. ESS re-authenticates the user and completes recovery controls.
2. A privileged backend calls `POST /api/ess/device/reset` with service bearer, signed `device_reset` assertion, request ID, and reset token.
3. The mobile app never receives the reset token.
4. The new device completes registration with a new key.

Copying a device ID is insufficient. Platform attestation adds a signal but does not replace signed claims or P-256 proof.
