import csv

import pytest

from app.validation.deployment import (
    REQUIRED_COLUMNS,
    bootstrap_threshold_ci,
    evaluate_results,
    threshold_at_target_fmr,
    validate_manifest,
)


def _row(pair_id, split, subject_a, subject_b, label, image_a, image_b, **values):
    row = {name: "controlled" for name in REQUIRED_COLUMNS}
    row.update({
        "pair_id": pair_id, "split": split, "subject_a": subject_a, "subject_b": subject_b,
        "label": str(label), "image_a": image_a, "image_b": image_b,
        "consent_reference": "consent-ref", "device_model": values.get("device_model", "phone-a"),
        "lighting_condition": values.get("lighting_condition", "office"),
        "environment": "indoor", "pose": "frontal", "quality_category": "good",
    })
    return row


def _write(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted(REQUIRED_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)


def test_manifest_detects_identity_and_image_leakage(tmp_path) -> None:
    path = tmp_path / "manifest.csv"
    _write(path, [
        _row("p1", "calibration", "subject-a", "subject-a", 1, "a1.jpg", "a2.jpg"),
        _row("p2", "test", "subject-a", "subject-a", 1, "a1.jpg", "a3.jpg"),
    ])
    result = validate_manifest(path, check_files=False)
    assert result.valid is False
    assert "identity_leakage_across_splits" in result.errors
    assert "image_leakage_across_splits" in result.errors


def test_valid_identity_disjoint_manifest(tmp_path) -> None:
    path = tmp_path / "manifest.csv"
    _write(path, [
        _row("p1", "calibration", "cal-a", "cal-a", 1, "c1.jpg", "c2.jpg"),
        _row("p2", "calibration", "cal-a", "cal-b", 0, "c1.jpg", "c3.jpg"),
        _row("p3", "test", "test-a", "test-a", 1, "t1.jpg", "t2.jpg"),
        _row("p4", "test", "test-a", "test-b", 0, "t1.jpg", "t3.jpg"),
    ])
    result = validate_manifest(path, check_files=False)
    assert result.valid is True
    assert result.genuine_pairs == 2
    assert result.impostor_pairs == 2


def test_demographic_fields_require_explicit_governance_approval(tmp_path) -> None:
    path = tmp_path / "manifest.csv"
    rows = [_row("p1", "calibration", "cal-a", "cal-a", 1, "c1.jpg", "c2.jpg")]
    rows[0]["demographic_approved_slice"] = "slice-a"
    fields = sorted(REQUIRED_COLUMNS | {"demographic_approved_slice"})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    assert "demographic_fields_require_governance_approval" in validate_manifest(
        path, check_files=False
    ).errors
    approved = validate_manifest(
        path, check_files=False,
        approved_demographic_fields={"demographic_approved_slice"},
        governance_approval_reference="approved-governance-ref",
    )
    assert approved.valid is True


def test_low_fmr_resolution_and_bootstrap_confidence_interval() -> None:
    results = [
        {"label": 0, "similarity_cosine": index / 1000, "split": "calibration"}
        for index in range(50)
    ] + [{"label": 1, "similarity_cosine": 0.8, "split": "calibration"} for _ in range(10)]
    _, resolvable = threshold_at_target_fmr(results, 1e-3)
    assert resolvable is False
    interval = bootstrap_threshold_ci(results, 0.1, samples=50)
    assert len(interval) == 2
    assert interval[0] <= interval[1]


def test_per_condition_slices_and_failure_latency_reporting() -> None:
    results = [
        {"label": 1, "similarity_cosine": 0.8, "split": "test", "total_ms": 100, "error_code": None, "device_model": "a", "lighting_condition": "office"},
        {"label": 0, "similarity_cosine": 0.1, "split": "test", "total_ms": 200, "error_code": None, "device_model": "a", "lighting_condition": "office"},
        {"label": 1, "similarity_cosine": None, "split": "test", "total_ms": 300, "error_code": "no_face", "device_model": "b", "lighting_condition": "outdoor"},
    ]
    report = evaluate_results(results, 0.4)
    assert report["failure_to_acquire_rate"] == pytest.approx(1 / 3)
    assert report["latency_ms"]["p95"] is not None
    assert "device_model:a" in report["slices"]
