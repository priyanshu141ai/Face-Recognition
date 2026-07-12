import argparse
import csv
import json
import random
import shutil
from itertools import combinations, product
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create deterministic identity-fold calibration pairs")
    parser.add_argument("--source", default="benchmark_data/lfw")
    parser.add_argument("--output", default="benchmark_data/lfw_phase5")
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=2025)
    args = parser.parse_args()
    source, output = Path(args.source), Path(args.output)
    with (source / "identities.csv").open("r", encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    by_subject: dict[str, list[str]] = {}
    for row in source_rows:
        by_subject.setdefault(row["subject_id"], []).append(row["image"])
    if len(by_subject) < 50 or any(len(images) < 2 for images in by_subject.values()):
        raise SystemExit("source needs at least 50 subjects with 2 images each")

    rng = random.Random(args.seed)
    subjects = sorted(by_subject)
    rng.shuffle(subjects)
    fold_by_subject = {subject: index % args.folds for index, subject in enumerate(subjects)}
    images_dir = output / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    identity_rows, pair_rows = [], []
    for subject, images in by_subject.items():
        fold = fold_by_subject[subject]
        for image in images:
            shutil.copy2(source / "images" / image, images_dir / image)
            identity_rows.append({"image": image, "subject_id": subject, "split": f"fold_{fold}"})
        for image_a, image_b in combinations(images, 2):
            pair_rows.append({
                "image_a": image_a, "image_b": image_b, "label": "1",
                "subject_a": subject, "subject_b": subject, "fold_a": fold, "fold_b": fold,
            })
    for subject_a, subject_b in combinations(subjects, 2):
        fold_a, fold_b = fold_by_subject[subject_a], fold_by_subject[subject_b]
        for image_a, image_b in product(by_subject[subject_a], by_subject[subject_b]):
            pair_rows.append({
                "image_a": image_a, "image_b": image_b, "label": "0",
                "subject_a": subject_a, "subject_b": subject_b, "fold_a": fold_a, "fold_b": fold_b,
            })
    rng.shuffle(pair_rows)
    for filename, fields, rows in (
        ("identities.csv", ["image", "subject_id", "split"], identity_rows),
        ("pairs.csv", ["image_a", "image_b", "label", "subject_a", "subject_b", "fold_a", "fold_b"], pair_rows),
    ):
        with (output / filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    fold_sizes = {str(fold): sum(value == fold for value in fold_by_subject.values()) for fold in range(args.folds)}
    (output / "manifest.json").write_text(json.dumps({
        "source": str(source), "seed": args.seed, "identity_disjoint": True,
        "protocol": "identity_kfold_cross_validation", "folds": args.folds,
        "subjects_per_fold": fold_sizes, "pairs": len(pair_rows),
    }, indent=2), encoding="utf-8")
    print(f"Prepared {len(pair_rows)} pairs across {args.folds} identity-disjoint folds at {output}")


if __name__ == "__main__":
    main()
