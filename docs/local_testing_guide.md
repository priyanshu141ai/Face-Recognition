# Local Testing Guide

Simple Hinglish guide for Windows local testing.

## A. Mock Mode Test

Mock mode API flow test karta hai. Real biometric recognition nahi hota.

```powershell
cd "C:\projects\Face Recognition\face-recognition-backend"
.\scripts\start_mock_mode.ps1
```

In another terminal:

```powershell
python scripts\check_active_model_mode.py --base-url http://127.0.0.1:8000 --expected mock
python scripts\run_all_quality_checks.py --mode mock --base-url http://127.0.0.1:8000
```

## B. Check Mock Ya Real

```powershell
python scripts\check_active_model_mode.py --base-url http://127.0.0.1:8000 --expected real
```

Browser:

```text
http://127.0.0.1:8000/v1/models/current
```

Real mode me expected:

```text
detector.name = yunet_2023mar_opencv
recognizer.name = arcface_r100_onnx
recognizer.embedding_dim = 512
```

## C. Place ONNX Files

Required:

```text
models/face_detection_yunet_2023mar.onnx
models/face-recognition-resnet100-arcface.onnx
```

Do not commit model files.

## D. Validate Model Files

```powershell
python scripts\validate_model_artifacts.py
python scripts\smoke_test_models.py
```

## E. Start Real Mode

```powershell
.\scripts\start_real_mode.ps1
```

## F. Test Single Image

```powershell
python scripts\manual_test_single_image.py "test_images\my face.png" --base-url http://127.0.0.1:8000
```

## G. Test Two Images

```powershell
python scripts\manual_test_compare_images.py "test_images\a.png" "test_images\b.png" --base-url http://127.0.0.1:8000
```

## H. Interpret Output

| Field | Meaning |
| --- | --- |
| `decision` | `match` or `non_match` |
| `similarity_cosine` | raw embedding similarity |
| `threshold.value` | cutoff used for decision |
| `match_score_percent` | current simple UX score, not real probability yet |

## I. Common Errors

| Error | Fix |
| --- | --- |
| mock mode active | restart with `start_real_mode.ps1` |
| `arcface_model_not_found` | place ArcFace ONNX in `models/` |
| `model_not_found` | check exact file name/path |
| `invalid_image_payload` | use valid JPG/PNG |
| `no_face_detected` | use clearer face image |
| `invalid_embedding_shape` | wrong ArcFace model output dimension |

## J. Run All Quality Checks

```powershell
python scripts\run_all_quality_checks.py --mode mock --base-url http://127.0.0.1:8000
python scripts\run_all_quality_checks.py --mode real --base-url http://127.0.0.1:8000
```

Exit codes: `0=PASS`, `1=FAIL`, `2=PASS_WITH_WARNINGS`.
