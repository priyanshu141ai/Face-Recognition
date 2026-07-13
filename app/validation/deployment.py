from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.benchmark.metrics import compute_benchmark_metrics


REQUIRED_COLUMNS = {
    "pair_id", "image_a", "image_b", "subject_a", "subject_b", "label", "split",
    "device_model", "camera_type", "lighting_condition", "environment", "pose",
    "quality_category", "glasses", "mask", "spoof_type", "capture_version",
    "consent_reference",
}
ALLOWED_SPLITS = {"calibration", "test"}


@dataclass(frozen=True)
class ManifestValidation:
    errors: list[str]
    warnings: list[str]
    rows: list[dict[str, str]]
    genuine_pairs: int
    impostor_pairs: int

    @property
    def valid(self) -> bool:
        return not self.errors


def _content_hash(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def validate_manifest(
    path: str | Path,
    *,
    check_files: bool = True,
    approved_demographic_fields: set[str] | None = None,
    governance_approval_reference: str | None = None,
) -> ManifestValidation:
    source = Path(path)
    errors: list[str] = []
    warnings: list[str] = []
    if not source.is_file():
        return ManifestValidation(["manifest_not_found"], [], [], 0, 0)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - fields)
        if missing:
            return ManifestValidation(["missing_columns:" + ",".join(missing)], [], [], 0, 0)
        rows = [dict(row) for row in reader]
    demographic_fields = {name for name in fields if name.startswith("demographic_")}
    populated_demographic_fields = {
        name for name in demographic_fields if any(row.get(name, "").strip() for row in rows)
    }
    approved = approved_demographic_fields or set()
    if populated_demographic_fields - approved or (populated_demographic_fields and not governance_approval_reference):
        errors.append("demographic_fields_require_governance_approval")

    seen_pairs: set[tuple[str, str]] = set()
    subject_splits: dict[str, set[str]] = defaultdict(set)
    path_splits: dict[str, set[str]] = defaultdict(set)
    content_paths: dict[str, str] = {}
    genuine = impostor = 0
    for index, row in enumerate(rows, start=2):
        split = row["split"].strip().lower()
        if split not in ALLOWED_SPLITS:
            errors.append(f"row_{index}:invalid_split")
        try:
            label = int(row["label"])
        except ValueError:
            label = -1
        if label not in {0, 1}:
            errors.append(f"row_{index}:invalid_label")
        else:
            genuine += label
            impostor += 1 - label
            same_subject = row["subject_a"] == row["subject_b"]
            if same_subject != (label == 1):
                errors.append(f"row_{index}:label_subject_mismatch")
        if any(not row[name].strip() for name in ("pair_id", "image_a", "image_b", "subject_a", "subject_b", "consent_reference")):
            errors.append(f"row_{index}:required_value_missing")
        if any(any(character.isspace() for character in row[name]) for name in ("subject_a", "subject_b")):
            errors.append(f"row_{index}:subject_id_not_pseudonymous")
        pair = tuple(sorted((row["image_a"], row["image_b"])))
        if pair in seen_pairs:
            errors.append(f"row_{index}:duplicate_pair")
        seen_pairs.add(pair)
        for subject in (row["subject_a"], row["subject_b"]):
            subject_splits[subject].add(split)
        for name in ("image_a", "image_b"):
            path_splits[row[name]].add(split)
            image_path = Path(row[name])
            if not image_path.is_absolute():
                image_path = source.parent / image_path
            if check_files and not image_path.is_file():
                errors.append(f"row_{index}:image_not_found:{name}")
            elif check_files:
                digest = _content_hash(image_path)
                prior = content_paths.get(digest)
                if prior and prior != str(image_path):
                    errors.append(f"row_{index}:duplicate_image_content")
                content_paths[digest] = str(image_path)
    if any(len(splits) > 1 for splits in subject_splits.values()):
        errors.append("identity_leakage_across_splits")
    if any(len(splits) > 1 for splits in path_splits.values()):
        errors.append("image_leakage_across_splits")
    if genuine == 0 or impostor == 0:
        warnings.append("both_genuine_and_impostor_pairs_are_required")
    return ManifestValidation(sorted(set(errors)), warnings, rows, genuine, impostor)


def threshold_at_target_fmr(results: list[dict[str, Any]], target_fmr: float) -> tuple[float, bool]:
    impostor = np.asarray([
        float(item["similarity_cosine"]) for item in results
        if int(item["label"]) == 0 and item.get("similarity_cosine") is not None
    ])
    if not 0 < target_fmr < 1 or len(impostor) == 0:
        raise ValueError("target_fmr and impostor scores are required")
    resolvable = len(impostor) >= int(np.ceil(1 / target_fmr))
    allowed = int(np.floor(target_fmr * len(impostor)))
    descending = np.sort(impostor)[::-1]
    threshold = float(np.nextafter(descending[min(allowed, len(descending) - 1)], np.inf))
    return threshold, resolvable


def bootstrap_threshold_ci(
    results: list[dict[str, Any]], target_fmr: float, *, samples: int = 500, seed: int = 2026
) -> list[float]:
    impostor = np.asarray([
        float(item["similarity_cosine"]) for item in results
        if int(item["label"]) == 0 and item.get("similarity_cosine") is not None
    ])
    if len(impostor) < 2:
        raise ValueError("at least two impostor scores are required")
    rng = np.random.default_rng(seed)
    thresholds = []
    for _ in range(samples):
        sampled = rng.choice(impostor, len(impostor), replace=True)
        allowed = int(np.floor(target_fmr * len(sampled)))
        descending = np.sort(sampled)[::-1]
        thresholds.append(float(np.nextafter(descending[min(allowed, len(descending) - 1)], np.inf)))
    return [float(value) for value in np.percentile(thresholds, [2.5, 97.5])]


def evaluate_results(
    results: list[dict[str, Any]], threshold: float, *, fairness_fields: set[str] | None = None,
    min_slice_pairs: int = 1,
) -> dict[str, Any]:
    test = [item for item in results if item.get("split") == "test"]
    metrics = compute_benchmark_metrics(test, threshold)
    latencies = [float(item["total_ms"]) for item in test if item.get("total_ms") is not None]
    failures = [item for item in test if item.get("error_code")]
    enrollment = [item for item in results if item.get("operation") == "enroll"]
    liveness = [
        item for item in results
        if item.get("liveness_label") in {"live", "spoof"} and item.get("liveness_approved") is not None
    ]
    live = [item for item in liveness if item["liveness_label"] == "live"]
    spoof = [item for item in liveness if item["liveness_label"] == "spoof"]
    slices: dict[str, dict[str, Any]] = {}
    slice_fields = {
        "device_model", "lighting_condition", "environment", "pose", "quality_category",
        *(fairness_fields or set()),
    }
    for field in sorted(slice_fields):
        for value in sorted({str(item.get(field, "unknown")) for item in test}):
            subset = [item for item in test if str(item.get(field, "unknown")) == value]
            if len(subset) < min_slice_pairs:
                continue
            slice_metrics = compute_benchmark_metrics(subset, threshold)
            slices[f"{field}:{value}"] = {
                key: slice_metrics[key]
                for key in ("genuine_pairs", "impostor_pairs", "fmr_at_threshold", "fnmr_at_threshold", "auc")
            }
    metrics.update({
        "failure_to_acquire_rate": len(failures) / len(test) if test else None,
        "failure_to_enroll_rate": (
            sum(bool(item.get("error_code")) for item in enrollment) / len(enrollment)
            if enrollment else None
        ),
        "no_face_rate": (
            sum(item.get("error_code") == "no_face_detected" for item in test) / len(test)
            if test else None
        ),
        "multiple_face_rejection_rate": (
            sum(item.get("error_code") == "multiple_faces_detected" for item in test) / len(test)
            if test else None
        ),
        "liveness_false_reject_rate": (
            sum(not bool(item["liveness_approved"]) for item in live) / len(live) if live else None
        ),
        "liveness_false_accept_rate": (
            sum(bool(item["liveness_approved"]) for item in spoof) / len(spoof) if spoof else None
        ),
        "latency_ms": {
            "p50": float(np.percentile(latencies, 50)) if latencies else None,
            "p95": float(np.percentile(latencies, 95)) if latencies else None,
            "p99": float(np.percentile(latencies, 99)) if latencies else None,
        },
        "slices": slices,
    })
    return metrics


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
