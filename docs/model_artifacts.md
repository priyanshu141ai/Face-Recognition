# Model Artifacts and Local Setup

## Required files
These files are required for real YuNet + ArcFace inference:

- models/face_detection_yunet_2023mar.onnx
- models/face-recognition-resnet100-arcface.onnx

## Optional files
These files are optional and only needed for additional benchmark comparisons:

- models/mobilefacenet.onnx
- InsightFace buffalo_l (installed/configured by the user)

## Where to place them
Place the model weights locally under the repository's models directory:

```text
models/face_detection_yunet_2023mar.onnx
models/face-recognition-resnet100-arcface.onnx
models/mobilefacenet.onnx
```

## Validation
Run:

```bash
python scripts/validate_model_artifacts.py
```

## Warning
Model weights may have separate licenses. The repository should not redistribute weights unless the license allows it.
