import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.benchmark.metrics import compute_benchmark_metrics
from app.validation.deployment import bootstrap_threshold_ci, evaluate_results, threshold_at_target_fmr, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--target-fmr", required=True, type=float)
    parser.add_argument("--min-genuine-pairs", required=True, type=int)
    parser.add_argument("--min-impostor-pairs", required=True, type=int)
    parser.add_argument("--approval-status", choices=["pending", "approved", "rejected"], default="pending")
    parser.add_argument("--approved-fairness-field", action="append", default=[])
    parser.add_argument("--governance-approval-reference")
    parser.add_argument("--min-slice-pairs", required=True, type=int)
    args = parser.parse_args()
    source = Path(args.results)
    results = json.loads(source.read_text(encoding="utf-8"))
    calibration = [item for item in results if item.get("split") == "calibration" and not item.get("error_code")]
    genuine = sum(int(item["label"]) == 1 for item in calibration)
    impostor = sum(int(item["label"]) == 0 for item in calibration)
    if genuine < args.min_genuine_pairs or impostor < args.min_impostor_pairs:
        raise SystemExit("Insufficient calibration pairs for the risk-owner supplied gates")
    providers = {item.get("model_name") for item in calibration}
    hashes = {item.get("model_sha256") for item in calibration}
    if len(providers) != 1 or len(hashes) != 1 or None in hashes:
        raise SystemExit("Calibration results must use one pinned recognizer artifact")
    threshold, resolvable = threshold_at_target_fmr(calibration, args.target_fmr)
    if not resolvable:
        raise SystemExit("Target FMR cannot be resolved with the available impostor pairs")
    metrics = compute_benchmark_metrics(calibration, threshold)
    fairness_fields = set(args.approved_fairness_field)
    if fairness_fields and not args.governance_approval_reference:
        raise SystemExit("Fairness fields require a governance approval reference")
    if args.min_slice_pairs <= 0:
        raise SystemExit("Minimum slice pairs must be positive")
    test_metrics = evaluate_results(
        results, threshold, fairness_fields=fairness_fields,
        min_slice_pairs=args.min_slice_pairs,
    )
    artifact = {
        "schema_version": 2,
        "calibration_version": f"deployment_{args.dataset_version}_{datetime.now(timezone.utc):%Y%m%d}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_provider": next(iter(providers)),
        "recognizer_provider": next(iter(providers)),
        "model_sha256": next(iter(hashes)),
        "detector_version": calibration[0].get("detector_used"),
        "preprocessing_version": calibration[0].get("preprocessing_version"),
        "alignment_version": "arcface_5point_112_v1",
        "dataset_version": args.dataset_version,
        "dataset_results_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "split_strategy": "identity_disjoint_calibration_test",
        "target_fmr": args.target_fmr,
        "threshold": threshold,
        "threshold_confidence_interval_95": bootstrap_threshold_ci(calibration, args.target_fmr),
        "pair_counts": {"genuine": genuine, "impostor": impostor},
        "operating_point": f"deployment_fmr_{args.target_fmr:.0e}",
        "approval_status": args.approval_status,
        "real_probability": False,
        "score_calibration": {"method": "none", "real_probability": False},
        "validation_metadata": {
            "fmr": metrics["fmr_at_threshold"],
            "fnmr": metrics["fnmr_at_threshold"],
            "test_pair_counts": {
                "genuine": test_metrics["genuine_pairs"],
                "impostor": test_metrics["impostor_pairs"],
            },
            "fnmr_at_threshold": test_metrics["fnmr_at_threshold"],
            "fmr_at_threshold": test_metrics["fmr_at_threshold"],
            "failure_to_acquire_rate": test_metrics["failure_to_acquire_rate"],
            "failure_to_enroll_rate": test_metrics["failure_to_enroll_rate"],
            "no_face_rate": test_metrics["no_face_rate"],
            "multiple_face_rejection_rate": test_metrics["multiple_face_rejection_rate"],
            "liveness_false_accept_rate": test_metrics["liveness_false_accept_rate"],
            "liveness_false_reject_rate": test_metrics["liveness_false_reject_rate"],
            "latency_ms": test_metrics["latency_ms"],
            "slices": test_metrics["slices"],
            "approved_fairness_fields": sorted(fairness_fields),
            "governance_approval_reference": args.governance_approval_reference,
            "minimum_reported_slice_pairs": args.min_slice_pairs,
            "risk_owner_min_genuine_pairs": args.min_genuine_pairs,
            "risk_owner_min_impostor_pairs": args.min_impostor_pairs,
        },
    }
    write_json(args.output, artifact)
    print(args.output)


if __name__ == "__main__":
    main()
