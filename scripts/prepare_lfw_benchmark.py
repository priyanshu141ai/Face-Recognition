import argparse
import csv
import json
import re
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
from PIL import Image
from sklearn.datasets._lfw import _check_fetch_lfw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a reproducible LFW model-comparison dataset")
    parser.add_argument("--output", default="benchmark_data/lfw")
    parser.add_argument("--identities", type=int, default=200)
    parser.add_argument("--images-per-identity", type=int, default=2)
    parser.add_argument("--impostor-pairs", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.identities < 2 or args.images_per_identity < 2:
        raise SystemExit("Need at least 2 identities and 2 images per identity")

    output = Path(args.output)
    images_dir = output / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    _, lfw_folder = _check_fetch_lfw(funneled=True, download_if_missing=True)
    identity_dirs = [
        path for path in sorted(Path(lfw_folder).iterdir())
        if path.is_dir() and len(list(path.glob("*.jpg"))) >= args.images_per_identity
    ]
    eligible = np.arange(len(identity_dirs))
    if len(eligible) < args.identities:
        raise SystemExit(f"Only {len(eligible)} eligible identities available")
    selected = rng.choice(eligible, size=args.identities, replace=False)

    files_by_identity: dict[int, list[str]] = {}
    identity_rows: list[dict[str, str]] = []
    for target in selected:
        source_images = sorted(identity_dirs[int(target)].glob("*.jpg"))
        chosen = rng.choice(source_images, size=args.images_per_identity, replace=False)
        identity = _safe_name(identity_dirs[int(target)].name)
        files_by_identity[int(target)] = []
        for ordinal, source_path in enumerate(chosen, 1):
            filename = f"{identity}_{ordinal:02d}.jpg"
            with Image.open(source_path) as image:
                image.convert("RGB").save(images_dir / filename, quality=95)
            files_by_identity[int(target)].append(filename)
            identity_rows.append({"image": filename, "subject_id": identity, "split": "benchmark"})

    rows: list[dict[str, str]] = []
    for names in files_by_identity.values():
        for image_a, image_b in combinations(names, 2):
            rows.append({"image_a": image_a, "image_b": image_b, "label": "1"})

    identity_pairs = list(combinations(files_by_identity, 2))
    rng.shuffle(identity_pairs)
    for identity_a, identity_b in identity_pairs[: args.impostor_pairs]:
        rows.append({
            "image_a": str(rng.choice(files_by_identity[identity_a])),
            "image_b": str(rng.choice(files_by_identity[identity_b])),
            "label": "0",
        })
    rng.shuffle(rows)
    with (output / "pairs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_a", "image_b", "label"])
        writer.writeheader()
        writer.writerows(rows)
    with (output / "identities.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "subject_id", "split"])
        writer.writeheader()
        writer.writerows(identity_rows)
    (output / "manifest.json").write_text(json.dumps({
        "dataset": "Labeled Faces in the Wild (LFW)",
        "seed": args.seed,
        "identities": args.identities,
        "images_per_identity": args.images_per_identity,
        "genuine_pairs": sum(row["label"] == "1" for row in rows),
        "impostor_pairs": sum(row["label"] == "0" for row in rows),
        "purpose": "research model comparison only",
    }, indent=2), encoding="utf-8")
    print(f"Prepared {len(rows)} pairs from {args.identities} identities at {output}")


if __name__ == "__main__":
    main()
