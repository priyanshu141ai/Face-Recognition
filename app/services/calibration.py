import json
import math
from pathlib import Path
from typing import Any

from app.core.errors import CalibrationProfileError


class ScoreCalibrator:
    def __init__(self, profile: dict[str, Any] | None = None) -> None:
        self.profile = profile
        self.version = profile["calibration_version"] if profile else "linear_fallback_v1"

    @classmethod
    def from_settings(cls, settings: Any) -> "ScoreCalibrator":
        provider = settings.recognizer_provider
        configured = settings.calibration_profile_path
        path = Path(configured) if configured else Path(settings.calibration_dir) / f"{provider}.json"
        if not path.exists():
            if settings.require_calibration and provider != "mock":
                raise CalibrationProfileError(f"calibration profile is required: {path}")
            return cls()
        try:
            profile = json.loads(path.read_text(encoding="utf-8"))
            cls._validate(profile, provider, settings)
            return cls(profile)
        except CalibrationProfileError:
            raise
        except Exception as exc:
            raise CalibrationProfileError(f"invalid calibration profile: {path}") from exc

    @staticmethod
    def _validate(profile: dict[str, Any], provider: str, settings: Any) -> None:
        required = {"schema_version", "calibration_version", "model_provider", "model_sha256", "threshold", "operating_point", "score_calibration"}
        if required - profile.keys() or profile["schema_version"] != 1:
            raise CalibrationProfileError("calibration profile schema is invalid")
        if profile["model_provider"] != provider:
            raise CalibrationProfileError("calibration profile provider mismatch")
        expected_sha = {
            "arcface_onnx": settings.arcface_sha256,
            "mobilefacenet_onnx": settings.mobilefacenet_sha256,
        }.get(provider)
        if expected_sha and profile["model_sha256"] != expected_sha:
            raise CalibrationProfileError("calibration profile model checksum mismatch")
        if not -1 <= float(profile["threshold"]) <= 1:
            raise CalibrationProfileError("calibration threshold is outside cosine range")
        score = profile["score_calibration"]
        if score.get("method") != "balanced_platt_logistic" or float(score.get("coefficient", 0)) <= 0:
            raise CalibrationProfileError("score calibration must be monotonic Platt scaling")

    @property
    def threshold(self) -> float | None:
        return float(self.profile["threshold"]) if self.profile else None

    @property
    def operating_point(self) -> str:
        return self.profile["operating_point"] if self.profile else "fixed_threshold_fallback"

    @property
    def real_probability(self) -> bool:
        return bool(self.profile and self.profile["score_calibration"].get("real_probability", False))

    def calibrate(self, similarity: float) -> float:
        if not self.profile:
            return round(float(max(0.0, min(100.0, similarity * 100.0))), 2)
        calibration = self.profile["score_calibration"]
        logit = float(calibration["coefficient"]) * similarity + float(calibration["intercept"])
        value = 100.0 / (1.0 + math.exp(-max(-60.0, min(60.0, logit))))
        return round(value, 2)

    def metadata(self) -> dict[str, Any]:
        return {
            "name": self.version,
            "real_probability": self.real_probability,
            "profile_loaded": self.profile is not None,
            "operating_point": self.operating_point,
        }


def resolve_match_policy(settings: Any) -> tuple[ScoreCalibrator, float]:
    calibrator = ScoreCalibrator.from_settings(settings)
    threshold = settings.match_threshold
    if calibrator.threshold is not None and settings.use_calibrated_threshold and not settings.match_threshold_override:
        threshold = calibrator.threshold
    return calibrator, float(threshold)
