from pathlib import Path

from app.validation.checks import check_benchmark_dataset


def test_invalid_pairs_csv_reports_fail(tmp_path: Path) -> None:
    images = tmp_path / "images"
    images.mkdir()
    (images / "a.jpg").write_bytes(b"fake")
    (images / "b.jpg").write_bytes(b"fake")
    (tmp_path / "pairs.csv").write_text("image_a,image_b,label\na.jpg,b.jpg,2\n", encoding="utf-8")
    results = check_benchmark_dataset(tmp_path)
    assert any(item.check_name == "Valid labels" and item.status == "FAIL" for item in results)


def test_readiness_rejects_duplicate_pairs(tmp_path: Path) -> None:
    from app.benchmark.model_artifacts import evaluate_benchmark_readiness

    images = tmp_path / "images"
    images.mkdir()
    (images / "a_1.jpg").write_bytes(b"fake")
    (images / "b_1.jpg").write_bytes(b"fake")
    (tmp_path / "pairs.csv").write_text(
        "image_a,image_b,label\na_1.jpg,b_1.jpg,0\nb_1.jpg,a_1.jpg,0\n",
        encoding="utf-8",
    )
    readiness = evaluate_benchmark_readiness(tmp_path)
    assert not readiness["ok"]
    assert any("duplicate pair" in error for error in readiness["errors"])


def test_readiness_rejects_empty_images(tmp_path: Path) -> None:
    from app.benchmark.model_artifacts import evaluate_benchmark_readiness

    images = tmp_path / "images"
    images.mkdir()
    (images / "a_1.jpg").write_bytes(b"")
    (images / "a_2.jpg").write_bytes(b"")
    (images / "b_1.jpg").write_bytes(b"")
    (tmp_path / "pairs.csv").write_text(
        "image_a,image_b,label\na_1.jpg,a_2.jpg,1\na_1.jpg,b_1.jpg,0\n",
        encoding="utf-8",
    )
    readiness = evaluate_benchmark_readiness(tmp_path)
    assert any("invalid or empty image" in error for error in readiness["errors"])
