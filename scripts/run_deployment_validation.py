import argparse
import csv
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.benchmark.runner import BenchmarkRunner
from app.validation.deployment import validate_manifest, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--detector", choices=["yunet", "mock"], default="yunet")
    parser.add_argument("--allow-mock", action="store_true")
    parser.add_argument("--approved-demographic-field", action="append", default=[])
    parser.add_argument("--governance-approval-reference")
    args = parser.parse_args()
    manifest = Path(args.manifest)
    approved_demographics = set(args.approved_demographic_field)
    validation = validate_manifest(
        manifest,
        approved_demographic_fields=approved_demographics,
        governance_approval_reference=args.governance_approval_reference,
    )
    if not validation.valid:
        raise SystemExit("Invalid deployment manifest: " + "; ".join(validation.errors))

    with tempfile.TemporaryDirectory(prefix="face_deployment_validation_") as directory:
        dataset = Path(directory)
        with (dataset / "pairs.csv").open("w", encoding="utf-8", newline="") as handle:
            fields = ["image_a", "image_b", "label", "split", "subject_a", "subject_b"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in validation.rows:
                values = dict(row)
                for name in ("image_a", "image_b"):
                    path = Path(values[name])
                    values[name] = str(path if path.is_absolute() else (manifest.parent / path).resolve())
                writer.writerow({name: values[name] for name in fields})
        raw = BenchmarkRunner(
            args.models, dataset, detector_provider=args.detector, allow_mock=args.allow_mock
        ).run()

    safe_results = []
    for index, result in enumerate(raw):
        row = validation.rows[index % len(validation.rows)]
        result.pop("image_a", None)
        result.pop("image_b", None)
        result.pop("subject_a", None)
        result.pop("subject_b", None)
        result.pop("error_message", None)
        result.update({
            "pair_id": row["pair_id"],
            "device_model": row["device_model"],
            "camera_type": row["camera_type"],
            "lighting_condition": row["lighting_condition"],
            "environment": row["environment"],
            "pose": row["pose"],
            "quality_category": row["quality_category"],
            "spoof_type": row["spoof_type"],
        })
        for field in approved_demographics:
            result[field] = row.get(field)
        safe_results.append(result)
    write_json(args.output, safe_results)
    print(args.output)


if __name__ == "__main__":
    main()
