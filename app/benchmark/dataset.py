import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BenchmarkPair:
    image_a_path: str
    image_b_path: str
    label: int
    split: str = "benchmark"
    subject_a: str | None = None
    subject_b: str | None = None
    fold_a: int | None = None
    fold_b: int | None = None


def load_benchmark_pairs(dataset_path: str | Path) -> list[BenchmarkPair]:
    base_path = Path(dataset_path)
    pairs_csv = base_path / "pairs.csv"
    if not pairs_csv.exists():
        raise FileNotFoundError("pairs.csv does not exist")

    pairs: list[BenchmarkPair] = []
    with pairs_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            label = int(row["label"])
            if label not in {0, 1}:
                raise ValueError(f"invalid label {row['label']}")

            image_a = (base_path / "images" / row["image_a"]).resolve()
            image_b = (base_path / "images" / row["image_b"]).resolve()
            if not image_a.exists() or not image_b.exists():
                raise FileNotFoundError(f"image path does not exist: {row['image_a']} or {row['image_b']}")
            pairs.append(BenchmarkPair(
                image_a_path=str(image_a),
                image_b_path=str(image_b),
                label=label,
                split=row.get("split") or "benchmark",
                subject_a=row.get("subject_a") or None,
                subject_b=row.get("subject_b") or None,
                fold_a=int(row["fold_a"]) if row.get("fold_a") not in {None, ""} else None,
                fold_b=int(row["fold_b"]) if row.get("fold_b") not in {None, ""} else None,
            ))
    return pairs
