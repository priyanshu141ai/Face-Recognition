# Liveness spoof-validation protocol

Status: **template only; no provider or spoof media has been tested**.

Use only approved, consented, licensed, non-employee or explicitly authorized test subjects/media in a controlled encrypted store. Never put captures, completed manifests, assertions, provider tokens, subject mappings, or media paths in Git/chat.

## Required presentation classes

- bona-fide live capture;
- printed photo;
- photo displayed on phone and monitor;
- recorded-video and video-call replay;
- camera/virtual-camera/injection attack where safely testable;
- 2D mask and approved 3D-mask test where available;
- low light, glare, glasses;
- low/high-end devices, Android/iOS, front-camera/resolution slices.

Residual risks must include rooted/jailbroken devices, camera hooking, virtual cameras, modified apps, emulator injection, compromised gateway/provider SDK, deepfakes, and advanced masks.

## Controlled manifest format

Store completed manifests outside Git. A safe schema is:

```csv
case_id,presentation_class,bona_fide,platform,device_tier,camera_class,resolution_class,lighting,eyewear,provider_mode,capture_reference,consent_reference,expected_class
```

`case_id` and references must be opaque; no names, employee IDs, raw paths, tokens, or media content. The controlled system separately records provider/product/version, SDK/app versions, test date, region, operator authorization, and deletion date.

## Metrics

- APCER and BPCER where applicable, with confidence intervals;
- pass/reject/indeterminate and capture-failure counts;
- latency p50/p95/p99;
- per-platform/device/lighting/attack slices;
- provider/session failures and retry/cost counts.

Security/risk owners must define sample sizes and acceptance thresholds before testing. Do not tune and report on the same identities/attacks without a held-out evaluation. Do not claim spoof resistance from one genuine capture or a small hand-picked attack set.

## Execution gate

Run only after a provider, official sandbox, approved credentials, authorized media, privacy/retention plan, and explicit user authorization exist. Printed-photo, screen-replay, video-replay, injection, and mask results are currently **BLOCKED**.
