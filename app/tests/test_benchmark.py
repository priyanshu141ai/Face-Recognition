import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.benchmark.dataset import BenchmarkPair, load_benchmark_pairs
from app.benchmark.metrics import compute_benchmark_metrics
from app.benchmark.report import generate_benchmark_report
from app.benchmark.runner import BenchmarkRunner
from app.models.mock_recognizer import MockFaceRecognizer


def _write_image(path: Path) -> None:
    from PIL import Image

    Image.new("RGB", (64, 64), color=(255, 0, 0)).save(path)


def test_pairs_csv_loading(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    _write_image(images_dir / "a.jpg")
    _write_image(images_dir / "b.jpg")
    _write_image(images_dir / "c.jpg")

    pairs_csv = tmp_path / "pairs.csv"
    pairs_csv.write_text("image_a,image_b,label\na.jpg,b.jpg,1\na.jpg,c.jpg,0\n", encoding="utf-8")

    pairs = load_benchmark_pairs(tmp_path)
    assert len(pairs) == 2
    assert isinstance(pairs[0], BenchmarkPair)
    assert pairs[0].label == 1


def test_invalid_pairs_csv_label_raises(tmp_path: Path) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    _write_image(images_dir / "a.jpg")
    _write_image(images_dir / "b.jpg")

    pairs_csv = tmp_path / "pairs.csv"
    pairs_csv.write_text("image_a,image_b,label\na.jpg,b.jpg,2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid label"):
        load_benchmark_pairs(tmp_path)


def test_missing_image_path_detection(tmp_path: Path) -> None:
    pairs_csv = tmp_path / "pairs.csv"
    pairs_csv.write_text("image_a,image_b,label\nmissing.jpg,other.jpg,0\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_benchmark_pairs(tmp_path)


def test_metrics_computation_on_synthetic_scores() -> None:
    results = [
        {"label": 1, "similarity_cosine": 0.95, "prediction": "match"},
        {"label": 1, "similarity_cosine": 0.90, "prediction": "match"},
        {"label": 0, "similarity_cosine": 0.20, "prediction": "non_match"},
        {"label": 0, "similarity_cosine": 0.10, "prediction": "non_match"},
    ]
    metrics = compute_benchmark_metrics(results, threshold=0.5)
    assert metrics["auc"] >= 0.0
    assert metrics["eer"] >= 0.0
    assert "fmr_at_threshold" in metrics
    assert metrics["fmr_resolution"] == 0.5
    assert not metrics["fmr_target_resolvable"]["1e-03"]


def test_eer_calculation_and_fmr_threshold() -> None:
    results = [
        {"label": 1, "similarity_cosine": 0.99},
        {"label": 1, "similarity_cosine": 0.98},
        {"label": 0, "similarity_cosine": 0.01},
        {"label": 0, "similarity_cosine": 0.02},
    ]
    metrics = compute_benchmark_metrics(results, threshold=0.5)
    assert metrics["eer"] >= 0.0
    assert metrics["fnmr_at_fmr_1e-3"] is None


def test_metrics_ignore_incomplete_results() -> None:
    results = [
        {"label": 1, "similarity_cosine": 0.95},
        {"label": 0, "similarity_cosine": None},
        {"label": None, "similarity_cosine": 0.1},
    ]
    metrics = compute_benchmark_metrics(results, threshold=0.5)
    assert metrics["labels"] == [1]
    assert len(metrics["genuine_scores"]) == 1
    assert abs(metrics["genuine_scores"][0] - 0.95) < 1e-6
    assert metrics["impostor_scores"] == []


def test_report_generation_creates_files(tmp_path: Path) -> None:
    results = [{"model_name": "mock", "label": 1, "similarity_cosine": 0.9, "prediction": "match", "error_code": None, "error_message": None, "decode_ms": 1.0, "detect_ms": 1.0, "align_ms": 1.0, "embed_ms": 1.0, "match_ms": 1.0, "total_ms": 4.0}]
    output_dir = tmp_path / "reports"
    paths = generate_benchmark_report(results, output_dir=output_dir, dataset_name="demo")
    assert paths["csv"].exists()
    assert paths["json"].exists()
    assert paths["markdown"].exists()


def test_report_uses_requested_threshold_and_unique_pair_counts(tmp_path: Path) -> None:
    common = {"image_a": "a.jpg", "image_b": "b.jpg", "label": 1, "similarity_cosine": 0.9, "total_ms": 1.0, "error_code": None, "embedding_dim": 16, "threshold": 0.7}
    paths = generate_benchmark_report([
        {"model_name": "m1", **common},
        {"model_name": "m2", **common},
    ], tmp_path, "threshold")
    summary = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert summary["genuine_pairs"] == 1
    assert all(model["threshold_used"] == 0.7 for model in summary["models"])


def test_runner_with_mock_recognizer(tmp_path: Path, monkeypatch) -> None:
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    _write_image(images_dir / "a.jpg")
    _write_image(images_dir / "b.jpg")

    pairs_csv = tmp_path / "pairs.csv"
    pairs_csv.write_text("image_a,image_b,label\na.jpg,b.jpg,1\n", encoding="utf-8")

    class FakeDetector:
        def detect(self, image_bytes, quality_policy=None):
            return [
                type("Detection", (), {"bbox_xywh": [0, 0, 10, 10], "landmarks5": [[10, 10], [20, 10], [15, 20], [10, 30], [20, 30]], "detection_confidence": 0.99, "model_dump": lambda self: {}})()
            ]

    monkeypatch.setattr("app.benchmark.runner.YuNetFaceDetector", lambda: FakeDetector())
    monkeypatch.setattr("app.benchmark.runner.FaceAligner", lambda: type("Aligner", (), {"align_face_112": lambda self, image, landmarks: np.zeros((112, 112, 3), dtype=np.uint8)})())

    runner = BenchmarkRunner(models=["mock"], dataset_path=tmp_path)
    results = runner.run()
    assert len(results) == 1
    assert results[0]["model_name"] == "mock"


def test_optional_recognizer_import_failure_gives_clean_error(monkeypatch) -> None:
    import importlib

    monkeypatch.setattr(importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("boom")))
    from app.models.insightface_buffalo_recognizer import InsightFaceBuffaloRecognizer

    with pytest.raises(RuntimeError, match="InsightFace is not installed"):
        InsightFaceBuffaloRecognizer()


def test_mock_detector_requires_explicit_opt_in(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="explicit"):
        BenchmarkRunner(models=["mock"], dataset_path=tmp_path, detector_provider="mock")
