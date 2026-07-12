from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from itertools import combinations
from typing import Any

from PIL import Image, UnidentifiedImageError

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover
    ort = None


REQUIRED_ARTIFACTS = [
    ("YuNet detector", "models/face_detection_yunet_2023mar.onnx", True),
    ("ArcFace ResNet100 ONNX", "models/face-recognition-resnet100-arcface.onnx", True),
    ("MobileFaceNet ONNX", "models/mobilefacenet.onnx", False),
]


def collect_model_artifact_statuses(models_dir: str | Path | None = None, root_dir: str | Path | None = None) -> list[dict[str, Any]]:
    base_dir = Path(models_dir or (root_dir or Path.cwd()) / "models")
    root = Path(root_dir or Path.cwd())
    statuses: list[dict[str, Any]] = []
    for name, relative_path, required in REQUIRED_ARTIFACTS:
        artifact_path = (base_dir / Path(relative_path).name).resolve() if base_dir.exists() else (root / relative_path).resolve()
        metadata = inspect_onnx_model(artifact_path) if artifact_path.exists() and artifact_path.suffix == ".onnx" else {"status": "MISSING" if not artifact_path.exists() else "NOT_CHECKED", "error": ""}
        if not artifact_path.exists():
            status = "MISSING"
        else:
            status = "FOUND"
        statuses.append({
            "name": name,
            "status": status,
            "path": str(artifact_path),
            "required": required,
            "metadata": metadata,
        })

    insightface_available = False
    try:
        import importlib.util
        insightface_available = importlib.util.find_spec("insightface") is not None
    except Exception:
        insightface_available = False

    statuses.append({
        "name": "InsightFace buffalo_l",
        "status": "FOUND" if insightface_available else "MISSING",
        "path": "optional package/model pack",
        "required": False,
    })
    return statuses


def format_model_artifact_table(statuses: list[dict[str, Any]]) -> str:
    headers = ["Model Artifact", "Status", "Path"]
    rows = [[item["name"], item["status"], item["path"]] for item in statuses]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(widths[idx], len(cell)) for idx, cell in enumerate(row)]
    def format_row(row: list[str]) -> str:
        return "  ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))
    return "\n".join([format_row(headers), format_row(["-" * width for width in widths]), *[format_row(row) for row in rows]])


def validate_model_artifacts(models_dir: str | Path | None = None, root_dir: str | Path | None = None) -> tuple[bool, list[dict[str, Any]]]:
    statuses = collect_model_artifact_statuses(models_dir=models_dir, root_dir=root_dir)
    required_missing = [item for item in statuses if item["required"] and item["status"] == "MISSING"]
    return len(required_missing) == 0, statuses


def inspect_onnx_model(model_path: str | Path) -> dict[str, Any]:
    path = Path(model_path)
    if not path.exists():
        return {"status": "MISSING", "error": "file does not exist"}
    if ort is None:
        return {"status": "UNAVAILABLE", "error": "onnxruntime is not installed"}
    try:
        session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        providers_available = ort.get_available_providers()
        return {
            "status": "LOADED",
            "input_names": [item.name for item in inputs],
            "input_shapes": [list(item.shape) for item in inputs],
            "output_names": [item.name for item in outputs],
            "output_shapes": [list(item.shape) for item in outputs],
            "providers_available": providers_available,
            "providers_selected": ["CPUExecutionProvider"],
        }
    except Exception as exc:  # pragma: no cover - defensive path
        return {"status": "ERROR", "error": str(exc)}


def evaluate_benchmark_readiness(dataset_path: str | Path) -> dict[str, Any]:
    base_path = Path(dataset_path)
    errors: list[str] = []
    if not (base_path / "pairs.csv").exists():
        errors.append("pairs.csv is missing")
        return {"ok": False, "errors": errors, "warnings": [], "genuine_pairs": 0, "impostor_pairs": 0, "identities": 0}

    if not (base_path / "images").exists():
        errors.append("images directory is missing")
        return {"ok": False, "errors": errors, "warnings": [], "genuine_pairs": 0, "impostor_pairs": 0, "identities": 0}

    with (base_path / "pairs.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    identity_map: dict[str, str] = {}
    identity_splits: dict[str, str] = {}
    identities_csv = base_path / "identities.csv"
    if identities_csv.exists():
        with identities_csv.open("r", encoding="utf-8", newline="") as handle:
            identity_rows = list(csv.DictReader(handle))
        identity_map = {row.get("image", ""): row.get("subject_id", "") for row in identity_rows}
        identity_splits = {row.get("image", ""): row.get("split", "") for row in identity_rows}
    if not rows:
        errors.append("pairs.csv does not contain any rows")

    genuine_pairs = 0
    impostor_pairs = 0
    identities: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()
    checked_images: set[Path] = set()
    for row in rows:
        label = row.get("label")
        if label not in {"0", "1"}:
            errors.append(f"invalid label {label!r} in pairs.csv")
            continue
        if int(label) == 1:
            genuine_pairs += 1
        else:
            impostor_pairs += 1
        names = [row.get("image_a", ""), row.get("image_b", "")]
        pair_identities = [identity_map.get(name, name.rsplit(".", 1)[0].rsplit("_", 1)[0]) for name in names]
        identities.update(pair_identities)
        if identity_map:
            if any(name not in identity_map for name in names):
                errors.append(f"identity metadata missing for pair: {names[0]} / {names[1]}")
            elif (pair_identities[0] == pair_identities[1]) != (label == "1"):
                errors.append(f"label conflicts with subject IDs: {names[0]} / {names[1]}")
            pair_split = row.get("split")
            image_splits = {identity_splits.get(name, "") for name in names}
            if pair_split and image_splits != {pair_split}:
                errors.append(f"pair crosses identity splits: {names[0]} / {names[1]}")
        pair_key = tuple(sorted(names))
        if names[0] == names[1]:
            errors.append(f"self-pair is not allowed: {names[0]}")
        elif pair_key in seen_pairs:
            errors.append(f"duplicate pair: {names[0]} / {names[1]}")
        seen_pairs.add(pair_key)
        image_a = (base_path / "images" / row.get("image_a", "")).resolve()
        image_b = (base_path / "images" / row.get("image_b", "")).resolve()
        if not image_a.exists() or not image_b.exists():
            errors.append(f"image path does not exist for pair {row.get('image_a')} / {row.get('image_b')}")
            continue
        for image_path in (image_a, image_b):
            if image_path in checked_images:
                continue
            checked_images.add(image_path)
            try:
                with Image.open(image_path) as image:
                    image.verify()
            except (OSError, UnidentifiedImageError):
                errors.append(f"invalid or empty image: {image_path.name}")
    if genuine_pairs == 0:
        errors.append("at least one genuine pair is required")
    if impostor_pairs == 0:
        errors.append("at least one impostor pair is required")
    warnings = []
    if len(identities) < 50:
        warnings.append(f"only {len(identities)} identities; use at least 50 for model comparison")
    if impostor_pairs < 1000:
        warnings.append(f"only {impostor_pairs} impostor pairs; FMR 1e-3 is not statistically resolved")
    if not identity_map:
        warnings.append("identities.csv missing; subject IDs were inferred from filenames")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "genuine_pairs": genuine_pairs, "impostor_pairs": impostor_pairs, "identities": len(identities)}


def generate_sample_pairs_csv(images_dir: str | Path, output_path: str | Path) -> Path:
    images_dir = Path(images_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image_paths = sorted(p.name for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    rows: list[dict[str, str]] = []
    by_prefix: dict[str, list[str]] = {}
    for image_name in image_paths:
        prefix = image_name.rsplit(".", 1)[0].rsplit("_", 1)[0] if "_" in image_name else image_name.rsplit(".", 1)[0]
        by_prefix.setdefault(prefix, []).append(image_name)

    for names in by_prefix.values():
        for image_a, image_b in combinations(names, 2):
            rows.append({"image_a": image_a, "image_b": image_b, "label": "1"})

    prefixes = sorted(by_prefix)
    for prefix_a, prefix_b in combinations(prefixes, 2):
        rows.append({"image_a": by_prefix[prefix_a][0], "image_b": by_prefix[prefix_b][0], "label": "0"})

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_a", "image_b", "label"])
        writer.writeheader()
        writer.writerows(rows)
    return output_path
