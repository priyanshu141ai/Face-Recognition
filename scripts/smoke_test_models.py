import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.models.arcface_onnx_recognizer import ArcFaceOnnxRecognizer
from app.models.yunet_detector import YuNetFaceDetector
from app.validation.checks import check_model_artifacts
from app.validation.report import ValidationReport, ValidationResult


def main() -> None:
    settings = get_settings()
    report = ValidationReport()
    report.extend(check_model_artifacts(settings, PROJECT_ROOT))

    if settings.detector_provider == "yunet" and Path(settings.yunet_model_path).exists():
        try:
            YuNetFaceDetector()
            report.add(ValidationResult("YuNet initialization", "Models", "PASS", "initialized"))
        except Exception as exc:
            report.add(ValidationResult("YuNet initialization", "Models", "FAIL", str(exc)))
    else:
        report.add(ValidationResult("YuNet initialization", "Models", "SKIP", f"provider={settings.detector_provider}"))

    if settings.recognizer_provider == "arcface_onnx" and Path(settings.arcface_model_path).exists():
        try:
            ArcFaceOnnxRecognizer()
            report.add(ValidationResult("ArcFace initialization", "Models", "PASS", "initialized"))
        except Exception as exc:
            report.add(ValidationResult("ArcFace initialization", "Models", "FAIL", str(exc)))
    else:
        report.add(ValidationResult("ArcFace initialization", "Models", "SKIP", f"provider={settings.recognizer_provider}"))

    report.print_table()
    raise SystemExit(0 if report.overall_status == "PASS" else 1)


if __name__ == "__main__":
    main()
