# Benchmarking Guide

## Goal
The benchmark harness compares recognizers under the same detection, alignment, embedding, and matching flow. It is meant for controlled model comparison and research, not for production threshold selection.

## Step 1: place model files
Place local model files under the models directory:

- models/face_detection_yunet_2023mar.onnx
- models/face-recognition-resnet100-arcface.onnx
- optional: models/mobilefacenet.onnx
- optional: InsightFace buffalo_l if installed/configured by the user

## Step 2: validate model files
```bash
python scripts/validate_model_artifacts.py
```

## Step 3: prepare benchmark data
Place image files under benchmark_data/images and define pairs in benchmark_data/pairs.csv. The repository includes a starter set.

```bash
python scripts/create_sample_pairs_csv.py --images benchmark_data/images --output benchmark_data/pairs.csv
```

## Step 4: check readiness
```bash
python scripts/check_benchmark_readiness.py
```

## Step 5: run a benchmark
ArcFace only:
```bash
python scripts/run_benchmark.py --dataset benchmark_data --models arcface_onnx --threshold 0.40 --output benchmark_reports
```

ArcFace vs MobileFaceNet:
```bash
python scripts/run_benchmark.py --dataset benchmark_data --models arcface_onnx mobilefacenet_onnx --threshold 0.40 --output benchmark_reports
```

Skip locally missing optional models:
```bash
python scripts/run_benchmark.py --dataset benchmark_data --models arcface_onnx mobilefacenet_onnx --skip-missing-models --output benchmark_reports
```

ArcFace vs MobileFaceNet vs buffalo_l:
```bash
python scripts/run_benchmark.py --dataset benchmark_data --models arcface_onnx mobilefacenet_onnx insightface_buffalo_l --threshold 0.40 --output benchmark_reports
```

## Dataset format
Place image files under benchmark_data/images and define pairs in benchmark_data/pairs.csv:

```csv
image_a,image_b,label
person001_1.jpg,person001_2.jpg,1
person001_1.jpg,person002_1.jpg,0
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
python scripts/run_benchmark.py --dataset benchmark_data --models arcface_onnx mobilefacenet_onnx --threshold 0.40 --output benchmark_reports
```

```powershell
python scripts/run_benchmark.py --dataset benchmark_data --models arcface_onnx mobilefacenet_onnx --threshold 0.40 --output benchmark_reports
```

## Report interpretation
Use benchmark outputs as research evidence only. Do not use the same threshold for production until it is selected on representative validation data.

## Safety notes
- Do not commit model weights.
- Do not compare models as equivalent if detector/alignment/preprocessing differs.
- Public benchmark numbers are not a replacement for your own identity-disjoint validation data.
