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
        configured = (
            settings.approved_calibration_profile_path
            if settings.require_approved_deployment_calibration
            else settings.calibration_profile_path
        )
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
        if required - profile.keys() or profile["schema_version"] not in {1, 2}:
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
        if score.get("method") == "balanced_platt_logistic":
            if float(score.get("coefficient", 0)) <= 0:
                raise CalibrationProfileError("score calibration must be monotonic Platt scaling")
        elif score.get("method") != "none" or score.get("real_probability") is not False:
            raise CalibrationProfileError("score calibration metadata is invalid")
        if settings.require_approved_deployment_calibration:
            ScoreCalibrator._validate_deployment_approval(profile, settings)

    @staticmethod
    def _validate_deployment_approval(profile: dict[str, Any], settings: Any) -> None:
        required = {
            "recognizer_provider", "detector_version", "preprocessing_version", "alignment_version",
            "dataset_version", "split_strategy", "target_fmr", "threshold_confidence_interval_95",
            "pair_counts", "created_at", "approval_status", "real_probability", "validation_metadata",
        }
        if profile.get("schema_version") != 2 or required - profile.keys():
            raise CalibrationProfileError("approved deployment calibration metadata is incomplete")
        if profile["approval_status"] != "approved":
            raise CalibrationProfileError("deployment calibration is not approved")
        if profile["recognizer_provider"] != settings.recognizer_provider:
            raise CalibrationProfileError("deployment calibration recognizer mismatch")
        expected_detector = "yunet_2023mar_opencv" if settings.detector_provider == "yunet" else settings.detector_provider
        if profile["detector_version"] != expected_detector:
            raise CalibrationProfileError("deployment calibration detector mismatch")
        if profile["preprocessing_version"] != "align112_rgb_v1":
            raise CalibrationProfileError("deployment calibration preprocessing mismatch")
        if profile["alignment_version"] != "arcface_5point_112_v1":
            raise CalibrationProfileError("deployment calibration alignment mismatch")
        if profile["split_strategy"] != "identity_disjoint_calibration_test":
            raise CalibrationProfileError("deployment calibration split strategy is unsafe")
        if profile["real_probability"] is not False:
            raise CalibrationProfileError("deployment match score is not an identity probability")
        counts = profile["pair_counts"]
        if int(counts.get("genuine", 0)) < settings.deployment_min_genuine_pairs:
            raise CalibrationProfileError("deployment calibration has insufficient genuine pairs")
        if int(counts.get("impostor", 0)) < settings.deployment_min_impostor_pairs:
            raise CalibrationProfileError("deployment calibration has insufficient impostor pairs")
        if float(profile["target_fmr"]) != float(settings.deployment_target_fmr):
            raise CalibrationProfileError("deployment calibration target FMR mismatch")
        validation = profile["validation_metadata"]
        test_counts = validation.get("test_pair_counts", {})
        if int(test_counts.get("genuine", 0)) < settings.deployment_min_genuine_pairs:
            raise CalibrationProfileError("deployment test has insufficient genuine pairs")
        if int(test_counts.get("impostor", 0)) < settings.deployment_min_impostor_pairs:
            raise CalibrationProfileError("deployment test has insufficient impostor pairs")
        if validation.get("fnmr_at_threshold") is None or float(validation["fnmr_at_threshold"]) > settings.deployment_max_fnmr_at_target_fmr:
            raise CalibrationProfileError("deployment FNMR gate failed")
        if validation.get("failure_to_acquire_rate") is None or float(validation["failure_to_acquire_rate"]) > settings.deployment_max_failure_to_acquire_rate:
            raise CalibrationProfileError("deployment acquisition gate failed")
        p95 = validation.get("latency_ms", {}).get("p95")
        if p95 is None or float(p95) > settings.deployment_max_p95_latency_ms:
            raise CalibrationProfileError("deployment latency gate failed")

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
        if calibration.get("method") == "none":
            return round(float(max(0.0, min(100.0, similarity * 100.0))), 2)
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
