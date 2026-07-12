import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.benchmark.threshold_calibration import evaluate_threshold, select_threshold_at_fmr
from app.core.config import Settings
from app.core.errors import CalibrationProfileError
from app.main import app
from app.services.calibration import ScoreCalibrator, resolve_match_policy


def _profile(path: Path, provider: str = "arcface_onnx", sha256: str = "abc") -> Path:
    path.write_text(json.dumps({
        "schema_version": 1,
        "calibration_version": "identity_5fold_platt_v1",
        "model_provider": provider,
        "model_sha256": sha256,
        "threshold": 0.55,
        "operating_point": "identity_5fold_fmr_1e-03",
        "score_calibration": {
            "method": "balanced_platt_logistic", "coefficient": 10.0,
            "intercept": -5.0, "real_probability": False,
        },
    }), encoding="utf-8")
    return path


def test_threshold_selection_is_tie_safe() -> None:
    genuine = np.linspace(0.4, 0.9, 20)
    impostor = np.concatenate([np.full(5, 0.3), np.linspace(-0.5, 0.2, 995)])
    scores = np.concatenate([genuine, impostor])
    labels = np.concatenate([np.ones(len(genuine)), np.zeros(len(impostor))])
    threshold = select_threshold_at_fmr(scores, labels, 1e-3)
    assert evaluate_threshold(scores, labels, threshold)["fmr"] <= 1e-3


def test_threshold_rejects_insufficient_tail_data() -> None:
    with pytest.raises(ValueError, match="at least 1000"):
        select_threshold_at_fmr(np.array([0.1, 0.9]), np.array([0, 1]), 1e-3)


def test_profile_drives_threshold_and_monotonic_score(tmp_path: Path) -> None:
    settings = Settings(
        recognizer_provider="arcface_onnx", arcface_sha256="abc",
        calibration_profile_path=str(_profile(tmp_path / "profile.json")),
    )
    calibrator, threshold = resolve_match_policy(settings)
    assert threshold == 0.55
    assert calibrator.calibrate(0.8) > calibrator.calibrate(0.2)


def test_explicit_threshold_overrides_profile(tmp_path: Path) -> None:
    settings = Settings(
        recognizer_provider="arcface_onnx", arcface_sha256="abc", match_threshold=0.7,
        match_threshold_override=True, calibration_profile_path=str(_profile(tmp_path / "profile.json")),
    )
    assert resolve_match_policy(settings)[1] == 0.7


def test_profile_checksum_mismatch_fails(tmp_path: Path) -> None:
    settings = Settings(
        recognizer_provider="arcface_onnx", arcface_sha256="expected",
        calibration_profile_path=str(_profile(tmp_path / "profile.json", sha256="wrong")),
    )
    with pytest.raises(CalibrationProfileError, match="checksum"):
        ScoreCalibrator.from_settings(settings)


def test_ready_fails_closed_when_required_profile_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "arcface_onnx")
    monkeypatch.setenv("REQUIRE_CALIBRATION", "true")
    monkeypatch.setenv("CALIBRATION_PROFILE_PATH", str(tmp_path / "missing.json"))
    response = TestClient(app).get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
