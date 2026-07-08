import json
from pathlib import Path

from app.benchmark.metrics import compute_benchmark_metrics
from app.benchmark.report import generate_benchmark_report
from app.validation.checks import check_benchmark_dataset


def test_benchmark_metrics_include_operating_points() -> None:
    results = [
        {"similarity_cosine": 0.9, "label": 1},
        {"similarity_cosine": 0.8, "label": 1},
        {"similarity_cosine": 0.1, "label": 0},
        {"similarity_cosine": 0.2, "label": 0},
    ]
    metrics = compute_benchmark_metrics(results, threshold=0.4)
    assert metrics["auc"] == 1.0
    assert metrics["fmr_at_threshold"] == 0.0
    assert metrics["fnmr_at_threshold"] == 0.0
    assert "fnmr_at_fmr_1e-5" in metrics


def test_benchmark_dataset_missing_columns_fails(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir()
    (tmp_path / "pairs.csv").write_text("a,b,label\nx.jpg,y.jpg,1\n", encoding="utf-8")
    results = check_benchmark_dataset(tmp_path)
    assert any(item.check_name == "pairs.csv columns" and item.status == "FAIL" for item in results)


def test_benchmark_report_writes_json_csv_markdown(tmp_path: Path) -> None:
    rows = [
        {"model_name": "mock", "label": 1, "similarity_cosine": 0.9, "total_ms": 1.0, "error_code": None, "embedding_dim": 16, "threshold": 0.4},
        {"model_name": "mock", "label": 0, "similarity_cosine": 0.1, "total_ms": 2.0, "error_code": None, "embedding_dim": 16, "threshold": 0.4},
    ]
    paths = generate_benchmark_report(rows, tmp_path, "strict")
    assert all(path.exists() for path in paths.values())
    summary = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert summary["genuine_pairs"] == 1
    assert summary["impostor_pairs"] == 1
