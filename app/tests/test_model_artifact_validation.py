from pathlib import Path

import pytest

from app.core.config import Settings
from app.validation.checks import check_model_artifacts


def test_optional_model_missing_reports_warn(tmp_path: Path) -> None:
    (tmp_path / "models").mkdir()
    settings = Settings(detector_provider="mock", recognizer_provider="mock")
    results = check_model_artifacts(settings, tmp_path)
    mobile = next(item for item in results if item.check_name == "MobileFaceNet ONNX")
    assert mobile.status == "WARN"


@pytest.mark.integration
def test_real_model_artifacts_present_for_integration() -> None:
    root = Path(__file__).resolve().parents[2]
    yunet = root / "models/face_detection_yunet_2023mar.onnx"
    arcface = root / "models/face-recognition-resnet100-arcface.onnx"
    if not yunet.exists() or not arcface.exists():
        pytest.skip("real ONNX model files are not available")
    settings = Settings(detector_provider="yunet", recognizer_provider="arcface_onnx")
    assert all(item.status != "FAIL" for item in check_model_artifacts(settings, root))
