# Face Recognition Backend Validation Guide

## Purpose
This guide explains how to verify the backend after Phase 4.1. The validation layer checks project structure, dependencies, model files, API behavior, benchmark readiness, logging safety, Docker readiness, and tests.

## What the validation checks
- Project structure and required files
- Python dependencies
- Environment configuration
- Model artifact paths and optional model availability
- API health, metadata, detect, and verify endpoints
- Mock-mode verification
- Controlled API errors
- Benchmark dataset readiness
- Dockerfile readiness
- Logging safety

## Run project structure check
```bash
python scripts/validate_project.py
```

## Run model artifact check
```bash
python scripts/validate_model_artifacts.py
python scripts/smoke_test_models.py
```

## Run API smoke test
Start the API first, then run:

```bash
python scripts/smoke_test_api.py --base-url http://127.0.0.1:8000
```

## Run benchmark readiness check
```bash
python scripts/smoke_test_benchmark.py --dataset benchmark_data
```

## Run full system check
```bash
python scripts/full_system_check.py --base-url http://127.0.0.1:8000 --dataset benchmark_data
```

Optional reports:
```bash
python scripts/full_system_check.py --json-output validation_report.json --md-output validation_report.md
```

## Mock mode validation
Windows PowerShell:
```powershell
$env:DETECTOR_PROVIDER="mock"
$env:RECOGNIZER_PROVIDER="mock"
uvicorn app.main:app --reload
```

Linux/Mac:
```bash
DETECTOR_PROVIDER=mock RECOGNIZER_PROVIDER=mock uvicorn app.main:app --reload
```

Then:
```bash
python scripts/full_system_check.py --base-url http://127.0.0.1:8000
```

## Real YuNet + ArcFace validation
Place:
```text
models/face_detection_yunet_2023mar.onnx
models/face-recognition-resnet100-arcface.onnx
```

Windows PowerShell:
```powershell
$env:DETECTOR_PROVIDER="yunet"
$env:RECOGNIZER_PROVIDER="arcface_onnx"
$env:YUNET_MODEL_PATH="models/face_detection_yunet_2023mar.onnx"
$env:ARCFACE_MODEL_PATH="models/face-recognition-resnet100-arcface.onnx"
uvicorn app.main:app --reload
```

Then:
```bash
python scripts/full_system_check.py --base-url http://127.0.0.1:8000 --dataset benchmark_data
```

## Optional integration tests
Integration tests run only when real ONNX files exist:
```bash
pytest -q -m integration
```

Normal CI tests do not require model weights:
```bash
pytest -q
```

## Common failures and fixes
- Missing YuNet model: place `models/face_detection_yunet_2023mar.onnx`.
- Missing ArcFace model: place `models/face-recognition-resnet100-arcface.onnx`.
- API smoke test fails: start `uvicorn app.main:app --reload`.
- Benchmark readiness fails: create `benchmark_data/images/` and `benchmark_data/pairs.csv`.
- Docker readiness fails: ensure `Dockerfile`, `requirements.txt`, `app/main.py`, and `models/` exist.
