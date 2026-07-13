# Deployment validation protocol

LFW is research evidence only. Production approval requires consented, representative captures from target phone classes and deployment conditions. Do not collect employee data automatically.

## Dataset rules

Use pseudonymous subject IDs and the template under `benchmark_data/deployment_template/`. Keep completed manifests and images outside Git. Record device/camera, lighting, indoor/outdoor, pose, quality/blur, glasses/mask where consented, spoof type, capture version, and consent reference. Demographic fields may be added only after legal, ethics, and risk-owner approval.

Subjects must be identity-disjoint between `calibration` and final `test`; image content must not cross splits; threshold selection uses calibration only. The final test set is evaluated once after threshold selection.

## Commands

```powershell
python scripts/prepare_deployment_validation_manifest.py --output <controlled-path>\manifest.csv
python scripts/validate_deployment_dataset.py --manifest <controlled-path>\manifest.csv
python scripts/run_deployment_validation.py --manifest <controlled-path>\manifest.csv --models arcface_onnx --output benchmark_reports\deployment\results.json
python scripts/generate_deployment_calibration.py --results benchmark_reports\deployment\results.json --output calibration\deployment-approved-candidate.json --dataset-version <version> --target-fmr <risk-approved> --min-genuine-pairs <risk-approved> --min-impostor-pairs <risk-approved> --min-slice-pairs <privacy-approved>
```

The generated artifact defaults to `approval_status=pending`. A risk owner must review representative ROC/AUC/EER, FMR/FNMR, confidence interval, failure-to-acquire, no/multiple-face rates, liveness spoof results, p50/p95/p99 latency, device/condition slices, consent/governance, and unresolved-low-FMR warnings before changing it to approved.

Production gates are configured through `DEPLOYMENT_*` variables. No universal values are supplied because the attendance threat model and business cost of false matches/non-matches must determine them. Match score percentage is not identity probability; clients use only backend `verified`/`decision`.
