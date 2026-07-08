# Developer Guide

## Quick start
1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Start the app with `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
4. Run tests with `pytest -q`.

## Main files to know
- [app/main.py](../app/main.py): app entrypoint and exception handling
- [app/api/v1/routes_faces.py](../app/api/v1/routes_faces.py): verification and face routes
- [app/services/pipeline.py](../app/services/pipeline.py): orchestration of the verification pipeline
- [app/models/yunet_detector.py](../app/models/yunet_detector.py): real YuNet detector implementation
- [app/models/arcface_onnx_recognizer.py](../app/models/arcface_onnx_recognizer.py): real ArcFace ONNX recognizer implementation
- [app/models/mock_detector.py](../app/models/mock_detector.py): fallback mock detector implementation
- [app/models/mock_recognizer.py](../app/models/mock_recognizer.py): mock recognizer implementation
- [app/schemas/face.py](../app/schemas/face.py): API request/response schema

## How the workflow works
A request enters the verification route, is decoded, passed through the configured detector, aligned, embedded, matched, and converted into a response payload.

## Editing tips
- Keep new model logic behind interfaces in the services and models folders.
- Avoid logging raw image payloads or embeddings.
- Update tests whenever the API contract changes.
