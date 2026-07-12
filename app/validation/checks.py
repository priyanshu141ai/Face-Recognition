from __future__ import annotations

import csv
import importlib.util
import re
from pathlib import Path
from typing import Any

from app.benchmark.model_artifacts import inspect_onnx_model
from app.core.config import Settings
from app.validation.report import ValidationResult, timed_result

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PROJECT_PATHS = [
    "app",
    "app/main.py",
    "app/core/config.py",
    "app/api/v1/routes_faces.py",
    "app/api/v1/routes_health.py",
    "app/api/v1/routes_models.py",
    "app/services/pipeline.py",
    "app/services/matcher.py",
    "app/services/alignment.py",
    "app/models/yunet_detector.py",
    "app/models/arcface_onnx_recognizer.py",
    "app/models/mock_detector.py",
    "app/models/mock_recognizer.py",
    "app/benchmark/dataset.py",
    "app/benchmark/runner.py",
    "app/benchmark/metrics.py",
    "app/benchmark/report.py",
    "models/.gitkeep",
    "benchmark_reports/.gitkeep",
    "requirements.txt",
    "Dockerfile",
    "README.md",
]

VERIFY_RESPONSE_KEYS = {
    "request_id",
    "decision",
    "match_score_percent",
    "similarity_cosine",
    "threshold",
    "model_versions",
    "faces",
    "timings_ms",
}
THRESHOLD_KEYS = {"score_type", "value", "operating_point"}
MODEL_VERSION_KEYS = {"detector", "recognizer", "preprocessing", "calibration"}
FACE_KEYS = {"image_a", "image_b"}
TIMING_KEYS = {"decode", "detect", "align", "embed", "match", "total"}
KNOWN_ERROR_CODES = {
    "invalid_image_payload",
    "no_face_detected",
    "multiple_faces_detected",
    "face_quality_rejected",
    "face_alignment_failed",
    "arcface_model_not_found",
    "arcface_inference_failed",
    "invalid_embedding_shape",
    "recognizer_provider_invalid",
    "detector_provider_invalid",
    "yunet_model_not_found",
    "model_not_found",
    "embedding_failed",
    "calibration_profile_invalid",
}


def check_file_exists(path: str | Path, category: str = "Project", required: bool = True) -> ValidationResult:
    path = Path(path)
    status = "PASS" if path.is_file() else ("FAIL" if required else "WARN")
    return ValidationResult(path.name, category, status, str(path))


def check_directory_exists(path: str | Path, category: str = "Project", required: bool = True) -> ValidationResult:
    path = Path(path)
    status = "PASS" if path.is_dir() else ("FAIL" if required else "WARN")
    return ValidationResult(path.name, category, status, str(path))


def check_required_project_structure(root: str | Path = PROJECT_ROOT) -> list[ValidationResult]:
    root = Path(root)
    missing = [item for item in REQUIRED_PROJECT_PATHS if not (root / item).exists()]
    return [
        ValidationResult(
            "Project structure",
            "Project",
            "FAIL" if missing else "PASS",
            "Missing: " + ", ".join(missing) if missing else "All required files found",
        ),
        check_file_exists(root / "requirements.txt", "Project"),
        check_file_exists(root / "Dockerfile", "Project"),
        check_directory_exists(root / "models", "Project"),
    ]


def check_python_dependencies(root: str | Path = PROJECT_ROOT) -> ValidationResult:
    root = Path(root)
    package_map = {
        "opencv-python-headless": "cv2",
        "python-multipart": "multipart",
        "pillow": "PIL",
        "pydantic-settings": "pydantic_settings",
        "python-dotenv": "dotenv",
        "scikit-learn": "sklearn",
        "uvicorn[standard]": "uvicorn",
    }
    missing: list[str] = []
    req = root / "requirements.txt"
    if not req.exists():
        return ValidationResult("Python dependencies", "Dependencies", "FAIL", "requirements.txt missing")
    for line in req.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        package = re.split(r"[=<>!~]", raw, maxsplit=1)[0].strip().lower()
        module = package_map.get(package, package.replace("-", "_"))
        if importlib.util.find_spec(module) is None:
            missing.append(package)
    return ValidationResult(
        "Python dependencies",
        "Dependencies",
        "FAIL" if missing else "PASS",
        "Missing: " + ", ".join(missing) if missing else "Installed",
    )


def check_env_config(settings: Settings) -> list[ValidationResult]:
    results = []
    detector_ok = settings.detector_provider in {"mock", "yunet"}
    recognizer_ok = settings.recognizer_provider in {"mock", "arcface_onnx", "mobilefacenet_onnx", "insightface_buffalo_l"}
    results.append(ValidationResult("Detector provider", "Environment", "PASS" if detector_ok else "FAIL", settings.detector_provider))
    results.append(ValidationResult("Recognizer provider", "Environment", "PASS" if recognizer_ok else "FAIL", settings.recognizer_provider))
    results.append(ValidationResult("Image size limit", "Environment", "PASS" if settings.max_image_mb > 0 else "FAIL", str(settings.max_image_mb)))
    results.append(ValidationResult("Match threshold", "Environment", "PASS" if -1 <= settings.match_threshold <= 1 else "FAIL", str(settings.match_threshold)))
    return results


def check_model_artifacts(settings: Settings, root: str | Path = PROJECT_ROOT) -> list[ValidationResult]:
    root = Path(root)
    artifacts = [
        ("YuNet detector", root / settings.yunet_model_path, settings.detector_provider == "yunet"),
        ("ArcFace ResNet100 ONNX", root / settings.arcface_model_path, settings.recognizer_provider == "arcface_onnx"),
        ("MobileFaceNet ONNX", root / settings.mobilefacenet_model_path, settings.recognizer_provider == "mobilefacenet_onnx"),
    ]
    results: list[ValidationResult] = []
    for name, path, required in artifacts:
        exists = path.exists()
        if exists and path.suffix == ".onnx":
            meta = inspect_onnx_model(path)
            detail = f"{path} ({meta['status']})"
        else:
            detail = str(path) if required else "Optional"
        status = "PASS" if exists else ("FAIL" if required else "WARN")
        results.append(ValidationResult(name, "Models", status, detail))

    insightface = importlib.util.find_spec("insightface") is not None
    results.append(ValidationResult("InsightFace buffalo_l", "Models", "PASS" if insightface else "WARN", "Optional package/model pack"))
    return results


def check_benchmark_dataset(dataset_path: str | Path) -> list[ValidationResult]:
    base = Path(dataset_path)
    pairs_csv = base / "pairs.csv"
    images_dir = base / "images"
    results = [
        ValidationResult("pairs.csv exists", "Benchmark", "PASS" if pairs_csv.exists() else "FAIL", str(pairs_csv)),
        ValidationResult("Image folder exists", "Benchmark", "PASS" if images_dir.exists() else "FAIL", str(images_dir)),
    ]
    if not pairs_csv.exists() or not images_dir.exists():
        return results

    errors: list[str] = []
    genuine = 0
    impostor = 0
    with pairs_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns_ok = reader.fieldnames == ["image_a", "image_b", "label"]
        rows = list(reader)
    results.append(ValidationResult("pairs.csv columns", "Benchmark", "PASS" if columns_ok else "FAIL", ",".join(reader.fieldnames or [])))

    for row in rows:
        label = row.get("label")
        if label not in {"0", "1"}:
            errors.append(f"invalid label {label!r}")
            continue
        genuine += label == "1"
        impostor += label == "0"
        if not (images_dir / row.get("image_a", "")).exists() or not (images_dir / row.get("image_b", "")).exists():
            errors.append(f"missing image for {row.get('image_a')} / {row.get('image_b')}")
    results.append(ValidationResult("Valid labels", "Benchmark", "FAIL" if any("label" in e for e in errors) else "PASS", "0/1 only"))
    results.append(ValidationResult("Image paths", "Benchmark", "FAIL" if any("missing image" in e for e in errors) else "PASS", "All pair images found"))
    results.append(ValidationResult("Genuine pairs", "Benchmark", "PASS" if genuine else "FAIL", f"{genuine} found"))
    results.append(ValidationResult("Impostor pairs", "Benchmark", "PASS" if impostor else "FAIL", f"{impostor} found"))
    return results


def check_api_response_shape(data: dict[str, Any]) -> ValidationResult:
    missing = VERIFY_RESPONSE_KEYS - data.keys()
    nested_missing = []
    if not missing:
        nested_missing += [f"threshold.{k}" for k in THRESHOLD_KEYS - set(data["threshold"].keys())]
        nested_missing += [f"model_versions.{k}" for k in MODEL_VERSION_KEYS - set(data["model_versions"].keys())]
        nested_missing += [f"faces.{k}" for k in FACE_KEYS - set(data["faces"].keys())]
        nested_missing += [f"timings_ms.{k}" for k in TIMING_KEYS - set(data["timings_ms"].keys())]
    all_missing = list(missing) + nested_missing
    return ValidationResult("Verify response schema", "API", "FAIL" if all_missing else "PASS", ", ".join(all_missing) if all_missing else "Schema OK")


def check_error_response_shape(data: dict[str, Any]) -> ValidationResult:
    detail = data.get("detail", data)
    if not isinstance(detail, dict):
        return ValidationResult("Error response schema", "API", "FAIL", "error body is not JSON object")
    error = detail.get("error")
    if not isinstance(error, dict) or "code" not in error or "message" not in error:
        return ValidationResult("Error response schema", "API", "FAIL", "missing error.code/error.message")
    status = "PASS" if error["code"] in KNOWN_ERROR_CODES else "WARN"
    return ValidationResult("Error response schema", "API", status, str(error["code"]))


def check_no_sensitive_logging_patterns(log_text: str) -> ValidationResult:
    patterns = ["data:image", "base64", "raw image", "authorization:", "bearer ", "embedding", "aligned crop", "traceback"]
    found = [p for p in patterns if p.lower() in log_text.lower()]
    return ValidationResult("Logging safety", "Security", "FAIL" if found else "PASS", "Found: " + ", ".join(found) if found else "No sensitive patterns found")


def check_logging_safety_static(root: str | Path = PROJECT_ROOT) -> ValidationResult:
    root = Path(root)
    logging_file = root / "app/core/logging.py"
    if not logging_file.exists():
        return ValidationResult("Logging safety", "Security", "FAIL", "logging.py missing")
    text = logging_file.read_text(encoding="utf-8")
    has_filter = "SensitiveDataFilter" in text and "base64" in text and "data:image" in text
    return ValidationResult("Logging safety", "Security", "PASS" if has_filter else "FAIL", "SensitiveDataFilter configured" if has_filter else "SensitiveDataFilter missing")


def check_docker_readiness(root: str | Path = PROJECT_ROOT) -> list[ValidationResult]:
    root = Path(root)
    dockerfile = root / "Dockerfile"
    checks = [
        check_file_exists(dockerfile, "Docker"),
        check_file_exists(root / "requirements.txt", "Docker"),
        check_file_exists(root / "app/main.py", "Docker"),
        check_directory_exists(root / "models", "Docker"),
    ]
    text = dockerfile.read_text(encoding="utf-8") if dockerfile.exists() else ""
    checks.append(ValidationResult("Docker uvicorn command", "Docker", "PASS" if "uvicorn" in text and "app.main:app" in text else "FAIL", "uvicorn app.main:app"))
    checks.append(ValidationResult("Docker port", "Docker", "PASS" if "EXPOSE 8080" in text else "FAIL", "EXPOSE 8080"))
    return checks
