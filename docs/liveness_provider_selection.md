# Liveness provider selection

Status: **WAITING FOR PROVIDER SELECTION**.

No named provider, official server-verification contract, sandbox, public verification keys, commercial approval, privacy terms, or credentials were found in this repository. The existing `external_assertion` adapter is generic HMAC plumbing; it is not evidence of real anti-spoof evaluation or provider approval.

## Current repository determination

- Provider selected: **No**.
- Local/runtime examples use `disabled`; `mock` is test-only.
- `external_assertion` has no named vendor, Android/iOS SDK, official signed-result
  contract, sandbox account, provider-session lookup, spoof evidence, licensing,
  privacy approval, or SLA. Its `production_capable` interface flag must not be
  treated as provider selection or production approval.
- No provider-specific code or test should be added until the decision record
  below is completed from official vendor material.

Selection must cover an Android and iOS capture SDK, official server-side result
verification, a signed result bound to the server challenge, user, device,
request ID and action, expiry and single-use replay controls, printed-photo,
screen and recorded-video replay detection, a usable sandbox, privacy/data-flow
terms, commercial licensing, and explicit fail-closed outage behavior.

## Required evidence package

The product/security owner must supply all applicable items before implementation:

- selected legal provider/product name and approved use case;
- official Android and iOS capture-SDK documentation and supported OS/device matrix;
- official server-side verification or result-lookup documentation;
- challenge, session, request, user/device, action, and app binding fields;
- signed result format, issuer/audience, allowed asymmetric algorithms, `kid`/JWKS rotation, and expiry/replay rules;
- sandbox endpoint/account and credentials stored outside Git;
- production versus sandbox separation and outage behavior;
- printed-photo, screen/video replay, injection, deepfake, and 2D/3D mask coverage or explicit limitations;
- independently reviewed APCER/BPCER or equivalent false-accept/reject evidence at the intended operating point;
- latency, rate limits, retry/idempotency, session expiry, and per-check cost;
- online/offline behavior and server-region/data-residency options, including India requirements;
- data flow, subprocessors, cross-border transfer, raw-media/template/result retention, deletion, breach, and DPA terms;
- consent/lawful-basis review for employee attendance;
- commercial licensing, redistribution constraints, SLA, support, version/EOL policy, and incident notification;
- sandbox spoof-test capability and result-signing-key rotation procedure.

Credentials, captures, assertions, keys, and completed test manifests must remain outside Git, chat, tickets, and general file shares.

## Approach comparison

| Approach | Strengths | Main limitations | Production decision |
| --- | --- | --- | --- |
| A. Commercial/external mobile SDK or service | Maintained capture SDK, server verification, threat research, device coverage, support/SLA | Cost, vendor/data transfer, SDK lock-in, opaque metrics, network dependency | Viable after contractual, privacy, sandbox, and independent spoof validation |
| B. Server-side passive anti-spoof model | More backend control; potentially provider-independent | Requires licensed/proven weights, representative training/validation, MLOps, injection-resistant capture provenance, and ongoing attack research | Not acceptable from an unknown/open model; needs formal model selection and validation |
| C. Active challenge only | Simple prompts and useful replay friction | Blink/head turn/multiple frames do not reliably stop prints, screens, injected video, or masks | **Insufficient as production anti-spoofing** |
| D. Hybrid | Provider PAD + server challenge + device proof + platform attestation + gateway binding | Highest integration/operational complexity | Preferred security architecture when proportional to attendance risk |

No vendor is recommended by this document. Selection is a product, security, privacy, legal, mobile, ESS, and operations decision.

## Mandatory technical acceptance gates

- Mobile cannot create or approve the trusted result.
- Face API/ESS verifies through official server-side cryptography or result lookup.
- Result binds provider session, local challenge, tenant, user, device, device-key version, gateway request ID, action, and capture time.
- Assertion uses explicit asymmetric algorithm and trusted rotating key ID where supported.
- Assertion/session is short-lived and single-use; sandbox results are rejected in production.
- Provider can return pass, reject, and indeterminate/outage distinctly.
- Fail-open is impossible for enrollment and attendance verification.
- Raw media and provider payloads are excluded from Face API logs and default persistence.
- Repeated request IDs do not create duplicate paid sessions.
- Rate/cost controls cover tenant, user, device, IP, provider session, and failure cooldown.
- Representative bona-fide and attack testing is approved and completed before rollout.

## Selection decision record

Complete this through the approved internal process, not in source code:

| Field | Required decision |
| --- | --- |
| Provider/product/version | Pending |
| Android/iOS scope | Pending |
| Verification mechanism | Pending |
| Sandbox/production endpoints | Pending |
| Signing algorithm/JWKS rotation | Pending |
| India region/privacy/DPA | Pending |
| Retention/deletion | Pending |
| Attack coverage/known limits | Pending |
| Accuracy and latency gates | Pending |
| Cost/rate limits | Pending |
| Outage/SLA/support | Pending |
| Security/privacy/legal approvers | Pending |

Implementation starts only after this evidence is available and the exact provider contract can be tested without exposing credentials or biometric media.
