# Face Recognition Backend

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green)](https://opensource.org/licenses/MIT)

## Purpose
This repository is a Phase 4.1 face verification backend. It has FastAPI APIs, YuNet detection, ArcFace ONNX recognition, benchmark tooling, and local model artifact validation.

## What this project does
The backend accepts two face images, validates them, runs a detector and embedding flow, and returns a verification decision with timing and model version metadata.

## Core workflow
The pipeline is intentionally split into clear stages:
1. ingestion
2. preprocessing
3. face detection
4. face selection
5. face alignment
6. embedding extraction
7. similarity matching
8. threshold decision
9. calibrated percentage scoring
10. response formatting

## Project structure
```text
app/
  main.py                 # FastAPI entrypoint
  api/v1/                 # Routes for health, faces, and models
  core/                   # Config, logging, errors, security
  schemas/                # Pydantic request/response models
  services/               # Decoder, alignment, matcher, calibration, pipeline
  models/                 # Mock, YuNet, ArcFace, MobileFaceNet, optional buffalo_l adapters
  tests/                  # API and unit tests
models/                  # Future model assets directory
scripts/                 # Placeholder model download scripts
docs/                    # API contract, phase plan, contributor workflow
```

## Where to edit what
- API routes: [app/api/v1](app/api/v1)
- Request/response shapes: [app/schemas](app/schemas)
- Verification logic: [app/services/pipeline.py](app/services/pipeline.py)
- Detector implementation: [app/models/yunet_detector.py](app/models/yunet_detector.py) and [app/models/mock_detector.py](app/models/mock_detector.py)
- Recognizer implementations: [app/models](app/models)
- Config and env vars: [app/core/config.py](app/core/config.py)
- Tests: [app/tests](app/tests)

## Phase 4 status
- Phase 3 ArcFace ONNX recognizer remains the default production recognizer
- Benchmark framework added for controlled model comparison
- ArcFace, MobileFaceNet, and optional InsightFace buffalo_l can be benchmarked against the same pipeline

## Phase 4.1 status
- Model artifact validation script added
- Benchmark readiness checker added
- Sample pairs.csv generator added
- Benchmark reports include dataset warning and model metadata

## Before running real inference
Place local model weights in the models directory before running real inference or benchmark jobs.

```bash
python scripts/validate_model_artifacts.py
```

### Windows PowerShell
```powershell
$env:DETECTOR_PROVIDER="yunet"
$env:RECOGNIZER_PROVIDER="arcface_onnx"
$env:YUNET_MODEL_PATH="models/face_detection_yunet_2023mar.onnx"
$env:ARCFACE_MODEL_PATH="models/face-recognition-resnet100-arcface.onnx"
uvicorn app.main:app --reload
```

### Linux/Mac
```bash
DETECTOR_PROVIDER=yunet RECOGNIZER_PROVIDER=arcface_onnx uvicorn app.main:app --reload
```

## Required model files
Place these files before running real inference:
- [models/face_detection_yunet_2023mar.onnx](models/face_detection_yunet_2023mar.onnx)
- [models/face-recognition-resnet100-arcface.onnx](models/face-recognition-resnet100-arcface.onnx)

Optional:
- [models/mobilefacenet.onnx](models/mobilefacenet.onnx)
- InsightFace buffalo_l, if installed and configured by the user

## Run locally
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Run in mock mode
```bash
DETECTOR_PROVIDER=mock RECOGNIZER_PROVIDER=mock uvicorn app.main:app --reload
```

### Run with YuNet + ArcFace
```bash
DETECTOR_PROVIDER=yunet RECOGNIZER_PROVIDER=arcface_onnx uvicorn app.main:app --reload
```

### Windows PowerShell
```powershell
$env:DETECTOR_PROVIDER="yunet"
$env:RECOGNIZER_PROVIDER="arcface_onnx"
$env:YUNET_MODEL_PATH="models/face_detection_yunet_2023mar.onnx"
$env:ARCFACE_MODEL_PATH="models/face-recognition-resnet100-arcface.onnx"
uvicorn app.main:app --reload
```

### Linux/Mac
```bash
DETECTOR_PROVIDER=yunet RECOGNIZER_PROVIDER=arcface_onnx uvicorn app.main:app --reload
```

## Example .env
```env
DETECTOR_PROVIDER=yunet
RECOGNIZER_PROVIDER=arcface_onnx
YUNET_MODEL_PATH=models/face_detection_yunet_2023mar.onnx
ARCFACE_MODEL_PATH=models/face-recognition-resnet100-arcface.onnx
YUNET_SCORE_THRESHOLD=0.85
YUNET_NMS_THRESHOLD=0.3
YUNET_TOP_K=5000
MIN_FACE_SIZE=20
MAX_IMAGE_DIMENSION=1920
ONNX_PROVIDERS=CPUExecutionProvider
MATCH_THRESHOLD=0.40
```

## Run tests
```bash
pytest -q
```

## How to check everything is working
```bash
pip install -r requirements.txt
pytest
python scripts/validate_project.py
python scripts/validate_model_artifacts.py
```

Start API in mock mode:
```bash
DETECTOR_PROVIDER=mock RECOGNIZER_PROVIDER=mock uvicorn app.main:app --reload
```

Then run:
```bash
python scripts/smoke_test_api.py --base-url http://127.0.0.1:8000
python scripts/full_system_check.py --base-url http://127.0.0.1:8000
```

Real mode only after placing ONNX files:
```bash
DETECTOR_PROVIDER=yunet RECOGNIZER_PROVIDER=arcface_onnx uvicorn app.main:app --reload
```

## Test verify endpoint
```bash
curl -X POST http://127.0.0.1:8000/v1/faces/verify -H "Content-Type: application/json" -d '{"request_id":"demo","image_a":{"kind":"base64_png","data":"<base64>"},"image_b":{"kind":"base64_png","data":"<base64>"}}'
```

## Local scripts
```bash
python scripts/validate_model_artifacts.py
python scripts/check_arcface_verification.py --image-a person1.jpg --image-b person2.jpg --save-crops outputs/aligned/
python scripts/extract_embedding.py --image person.jpg --output embedding.npy
```

## Benchmark workflow
```bash
python scripts/create_sample_pairs_csv.py --images benchmark_data/images --output benchmark_data/pairs.csv
python scripts/check_benchmark_readiness.py --dataset benchmark_data
python scripts/run_benchmark.py --dataset benchmark_data --models arcface_onnx --threshold 0.40 --output benchmark_reports
python scripts/run_benchmark.py --dataset benchmark_data --models arcface_onnx mobilefacenet_onnx --skip-missing-models --output benchmark_reports
python scripts/compare_models.py --reports benchmark_reports
```

## Run with Docker
```bash
docker build -t face-recognition-backend .
docker run -p 8000:8000 face-recognition-backend
```

## Contributor workflow
- Start with the route contract in [docs/api_contract.md](docs/api_contract.md)
- Follow the processing flow in [app/services/pipeline.py](app/services/pipeline.py)
- Read [docs/developer_guide.md](docs/developer_guide.md) for a faster onboarding path
- Keep mock implementations isolated so they can be replaced later
- Add or update tests when changing behavior

## Next phases
- Phase 5: calibrate thresholds with validation data
- Phase 6: add production security, monitoring, and deployment automation
