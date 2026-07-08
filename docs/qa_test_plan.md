# QA Test Plan

This plan exists to prevent silent mistakes like running the API in mock mode while assuming real YuNet + ArcFace is active.

## A. Test Strategy

| Test type | Purpose | Examples |
| --- | --- | --- |
| Unit tests | Validate small pure functions/classes. | matcher math, alignment, schema helpers |
| API contract tests | Keep request/response JSON stable. | `/v1/faces/verify` required fields |
| Smoke tests | Quickly verify a running API. | health, ready, models, detect, verify |
| Integration tests | Exercise real model adapters when local files exist. | YuNet init, ArcFace embedding |
| Real model tests | Confirm model files, shapes, dimensions, providers. | ArcFace output `[1,512]` |
| Benchmark tests | Validate pairs.csv, metrics, report generation. | ROC/AUC/EER synthetic scores |
| Security/logging tests | Prevent sensitive leakage. | no base64, tokens, embeddings |
| Performance sanity tests | Catch obvious latency regressions. | p50/p95 for mock verify |
| Failure-mode tests | Ensure controlled JSON errors. | bad base64, missing model, invalid provider |

PASS means required behavior is correct for the selected mode.
WARN means optional dependency/data/model is missing or not running.
FAIL means a required check failed and must be fixed before demo or release.

## B. Mode Matrix

| Mode | DETECTOR_PROVIDER | RECOGNIZER_PROVIDER | Model files required | Purpose |
| --- | --- | --- | --- | --- |
| mock | mock | mock | No | CI/API flow test |
| real detector only | yunet | mock | YuNet only | YuNet detection test |
| real recognition | yunet | arcface_onnx | YuNet + ArcFace | Real verification test |
| mobilefacenet benchmark | yunet | mobilefacenet_onnx | YuNet + MobileFaceNet | Optional benchmark |
| buffalo_l benchmark | optional | insightface_buffalo_l | Optional package | Optional benchmark |

## C. Endpoint Matrix

| Endpoint | Mock mode | Real detector | Real recognition | Error cases |
| --- | --- | --- | --- | --- |
| `GET /healthz` | Must return `{"status":"ok"}` | Same | Same | Server down |
| `GET /readyz` | Controlled ready response | Same | Same | Config issues should be caught by scripts |
| `GET /v1/models/current` | Must show mock names | Must show YuNet + mock recognizer | Must show YuNet + ArcFace 512 | Mode mismatch |
| `POST /v1/faces/detect` | Mock face response | Real face or controlled no-face | Same | bad image, no face, multiple faces |
| `POST /v1/faces/embed` | No embedding unless allowed | No embedding unless allowed | Real embedding only if allowed | model/provider errors |
| `POST /v1/faces/verify` | 200 success in mock | 200 or controlled no-face | 200 or controlled no-face | invalid payload/model/alignment |

## D. Image Test Matrix

| Image case | Expected |
| --- | --- |
| valid jpg | 200 in mock or controlled real response |
| valid png | 200 in mock or controlled real response |
| invalid base64 | controlled `invalid_image_payload` |
| corrupted image | controlled `invalid_image_payload` |
| blank image | mock 200 or real `no_face_detected` |
| no-face image | mock 200 or real `no_face_detected` |
| one clear face | real detect/verify should work if model detects it |
| multiple faces | `multiple_faces_detected` if policy rejects |
| tiny face | no-face or quality rejection |
| large image | accepted if under `MAX_IMAGE_MB` |
| rotated / EXIF | should not crash; orientation support is limited |
| grayscale | should decode or return controlled error |
| RGBA transparent PNG | should decode or return controlled error |
| file name spaces | manual scripts must handle quoted paths |
| unsupported format | schema/decoder rejects |
| oversized payload | controlled error, no crash |

## E. Model File Matrix

| Case | Expected |
| --- | --- |
| missing YuNet file | fail in real detector mode |
| missing ArcFace file | fail in real recognition mode |
| wrong file name | fail with path details |
| invalid ONNX file | fail load/metadata check |
| wrong input shape | fail/warn depending model and mode |
| wrong output dimension | fail `invalid_embedding_shape` |
| provider unavailable | fail or warn with provider details |
| model path contains spaces | must work when quoted/env var set |
| Windows path issues | use relative `models/...` or quoted absolute path |

## Required Pre-Demo Commands

```powershell
python scripts\run_all_quality_checks.py --mode mock --skip-api
python scripts\validate_model_artifacts.py
python scripts\check_active_model_mode.py --base-url http://127.0.0.1:8000 --expected real
```

Exit codes: `0=PASS`, `1=FAIL`, `2=PASS_WITH_WARNINGS` such as optional MobileFaceNet missing.
