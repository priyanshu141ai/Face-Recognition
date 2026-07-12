import csv
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from app.benchmark.model_artifacts import collect_model_artifact_statuses, evaluate_benchmark_readiness, generate_sample_pairs_csv


def test_validate_model_artifacts_reports_missing_files_cleanly(tmp_path: Path) -> None:
    statuses = collect_model_artifact_statuses(models_dir=tmp_path / "models", root_dir=tmp_path)
    required = [item for item in statuses if item["required"]]
    assert any(item["name"] == "YuNet detector" and item["status"] == "MISSING" for item in required)
    assert any(item["name"] == "ArcFace ResNet100 ONNX" and item["status"] == "MISSING" for item in required)


def test_check_benchmark_readiness_catches_missing_pairs_csv(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir(parents=True)
    readiness = evaluate_benchmark_readiness(tmp_path)
    assert readiness["ok"] is False
    assert "pairs.csv" in readiness["errors"][0]


def test_check_benchmark_readiness_catches_invalid_label(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "a.jpg").write_bytes(b"fake")
    (images_dir / "b.jpg").write_bytes(b"fake")
    pairs_csv = tmp_path / "pairs.csv"
    pairs_csv.write_text("image_a,image_b,label\na.jpg,b.jpg,2\n", encoding="utf-8")

    readiness = evaluate_benchmark_readiness(tmp_path)
    assert readiness["ok"] is False
    assert any("label" in error.lower() for error in readiness["errors"])


def test_create_sample_pairs_csv_creates_expected_output(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True)
    (images_dir / "person001_1.jpg").write_bytes(b"img")
    (images_dir / "person001_2.jpg").write_bytes(b"img")
    (images_dir / "person002_1.jpg").write_bytes(b"img")

    output_path = tmp_path / "pairs.csv"
    generated = generate_sample_pairs_csv(images_dir=images_dir, output_path=output_path)

    assert generated.exists()
    with generated.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) >= 2
    assert rows[0]["label"] in {"0", "1"}


def test_run_benchmark_skips_missing_optional_model_when_requested(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "run_benchmark.py"
    dataset = tmp_path / "dataset"
    images = dataset / "images"
    images.mkdir(parents=True)
    for name in ("a_1.jpg", "a_2.jpg", "b_1.jpg"):
        Image.new("RGB", (64, 64), color=(128, 128, 128)).save(images / name)
    (dataset / "pairs.csv").write_text("image_a,image_b,label\na_1.jpg,a_2.jpg,1\na_1.jpg,b_1.jpg,0\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script), "--dataset", str(dataset), "--models", "arcface_onnx", "mobilefacenet_onnx", "--skip-missing-models", "--detector", "mock", "--allow-mock", "--output", str(tmp_path / "reports")],
        capture_output=True,
        text=True,
        cwd=repo_root,
    )

    assert result.returncode == 0, result.stderr
    assert "Benchmark complete" in result.stdout
