# Phase Plan

Use this file as the roadmap for the backend evolution. Each phase should be implemented by replacing one mock component at a time.

## Phase 1: backend scaffold and mock pipeline
- Create the FastAPI project structure
- Define request/response schemas and stable API contracts
- Implement mock detector, recognizer, matcher, and calibration services
- Add validation, logging, Docker support, and tests

## Phase 2: integrate YuNet real detector
- Replace the mock detector with OpenCV FaceDetectorYN
- Preserve the same output schema for bounding boxes, landmarks, and confidence
- Keep the recognizer mocked while the detector becomes real

## Phase 3: integrate ArcFace ResNet100 ONNX recognizer
- Swap the mock recognizer for an ONNX Runtime implementation
- Keep embedding extraction behind the same service interface

## Phase 4: benchmarking buffalo_l, FaceNet, MobileFaceNet
- Compare detection and recognition quality across multiple models
- Gather timing and quality metrics for future tuning

## Phase 4.1: model artifact validation and real benchmark workflow
- Keep model weights out of Git
- Validate required YuNet and ArcFace artifacts locally
- Prepare benchmark_data readiness checks and sample pairs.csv generation
- Run real ArcFace/MobileFaceNet/buffalo_l benchmarks from local model files

## Phase 5: threshold calibration and validation dataset
- Tune decision thresholds using a validation dataset
- Move from mock calibration to a more realistic scoring policy

## Phase 6: production security, monitoring, deployment, CI/CD
- Add stronger auth, metrics, tracing, deployment automation, and observability
