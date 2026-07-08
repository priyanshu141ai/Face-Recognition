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
