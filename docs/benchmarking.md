# Benchmarking Guide

## Goal
The benchmark harness compares recognizers under the same detection, alignment, embedding, and matching flow. It is meant for controlled model comparison and research, not for production threshold selection.

## Step 1: model files
Place local model files under `models/`:

- models/face_detection_yunet_2023mar.onnx
- models/face-recognition-resnet100-arcface.onnx
- models/mobilefacenet.onnx (official InsightFace buffalo_sc `w600k_mbf.onnx`)
- optional: InsightFace buffalo_l if installed/configured by the user

## Step 2: validate model files
```bash
python scripts/validate_model_artifacts.py
```

MobileFaceNet is pinned to SHA-256 `9cc6e4a75f0e2bf0b1aed94578f144d15175f357bdc05e815e5c4a02b319eb4f`. InsightFace pretrained weights are non-commercial research only.

## Step 3: prepare benchmark data
Download and deterministically prepare the local LFW research set (200 identities, 10,200 pairs):

```bash
python scripts/prepare_lfw_benchmark.py
```

## Step 4: check readiness
```bash
python scripts/check_benchmark_readiness.py --dataset benchmark_data/lfw
```

## Step 5: run a benchmark
ArcFace only:
```bash
python scripts/run_benchmark.py --dataset benchmark_data/lfw --models arcface_onnx --output benchmark_reports/phase4_lfw
```

ArcFace vs MobileFaceNet:
```bash
python scripts/run_benchmark.py --dataset benchmark_data/lfw --models arcface_onnx mobilefacenet_onnx --output benchmark_reports/phase4_lfw
```

Skip locally missing optional models:
```bash
python scripts/run_benchmark.py --dataset benchmark_data/lfw --models arcface_onnx mobilefacenet_onnx --skip-missing-models --output benchmark_reports/phase4_lfw
```

ArcFace vs MobileFaceNet vs buffalo_l:
```bash
python scripts/run_benchmark.py --dataset benchmark_data/lfw --models arcface_onnx mobilefacenet_onnx insightface_buffalo_l --output benchmark_reports/phase4_lfw
```

## Dataset format
Custom datasets need `images/`, `pairs.csv`, and preferably `identities.csv`:

```csv
image_a,image_b,label
person001_1.jpg,person001_2.jpg,1
person001_1.jpg,person002_1.jpg,0
```

```csv
image,subject_id,split
person001_1.jpg,person001,benchmark
```

## Model providers
- arcface_onnx (default production recognizer)
- mobilefacenet_onnx
- insightface_buffalo_l (optional, install requirements-benchmark.txt)

## Metrics
- AUC
- EER
- FMR/FAR
- FNMR/FRR
- FNMR at FMR targets 1e-3, 1e-4, 1e-5

## Commands
```bash
python scripts/run_benchmark.py --dataset benchmark_data/lfw --models arcface_onnx mobilefacenet_onnx --output benchmark_reports/phase4_lfw
```

```powershell
python scripts/run_benchmark.py --dataset benchmark_data/lfw --models arcface_onnx mobilefacenet_onnx --output benchmark_reports/phase4_lfw
```

## Report interpretation
Use benchmark outputs as research evidence only. Do not use the same threshold for production until it is selected on representative validation data.

## Safety notes
- Do not commit model weights.
- Do not compare models as equivalent if detector/alignment/preprocessing differs.
- Public benchmark numbers are not a replacement for your own identity-disjoint validation data.
- FMR is reported only when the impostor-pair count can empirically resolve the target.
- Model-specific thresholds belong to Phase 5; Phase 4 comparisons prioritize AUC/EER and latency.
