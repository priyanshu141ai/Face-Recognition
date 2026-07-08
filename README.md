# Face Recognition Backend

## Purpose
This repository is a Phase 1 scaffold for a face verification backend. It is designed to give app developers a stable API contract while keeping the core inference pipeline modular and easy to replace later with real models.

## What this project does
The backend accepts two face images, validates them, runs a mock detection and embedding flow, and returns a verification decision with timing and model version metadata.

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
  services/               # Decoder, matcher, calibration, pipeline
  models/                 # Mock detector and recognizer implementations
  tests/                  # API and unit tests
models/                  # Future model assets directory
scripts/                 # Placeholder model download scripts
docs/                    # API contract, phase plan, contributor workflow
```

## Where to edit what
- API routes: [app/api/v1](app/api/v1)
- Request/response shapes: [app/schemas](app/schemas)
- Verification logic: [app/services/pipeline.py](app/services/pipeline.py)
- Detector implementation: [app/models/mock_detector.py](app/models/mock_detector.py)
- Recognizer implementation: [app/models/mock_recognizer.py](app/models/mock_recognizer.py)
- Config and env vars: [app/core/config.py](app/core/config.py)
- Tests: [app/tests](app/tests)

## Run locally
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run tests
```bash
pytest -q
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
- Phase 2: replace the mock detector with YuNet
- Phase 3: replace the mock recognizer with ArcFace ONNX
- Phase 4: benchmark additional face models
- Phase 5: calibrate thresholds with validation data
- Phase 6: add production security, monitoring, and deployment automation
