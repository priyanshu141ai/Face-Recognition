import json

import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings, validate_deployment_settings
from app.core.errors import CalibrationProfileError


def _secure(**overrides) -> Settings:
    values = {
        "environment": "production",
        "api_bearer_token": "service-secret",
        "gateway_assertion_required": True,
        "allow_unsigned_identity_headers": False,
        "gateway_assertion_issuer": "https://gateway.example.com",
        "gateway_assertion_audience": "face-api",
        "gateway_allowed_tenants": "tenant-001",
        "gateway_jwks_path": "gateway-public.jwks.json",
        "require_recent_device_attestation": True,
        "allowed_attestation_app_identifiers": "com.example.ess",
        "biometric_encryption_key": Fernet.generate_key().decode("ascii"),
        "device_reset_token": "admin-secret",
        "cors_allowed_origins": "https://ess.example",
        "enable_api_docs": False,
        "detector_provider": "yunet",
        "recognizer_provider": "arcface_onnx",
        "require_calibration": True,
        "liveness_required": True,
        "liveness_provider": "external_assertion",
        "liveness_assertion_secret": "provider-secret",
        "device_proof_required": True,
        "database_url": "postgresql+psycopg://user:pass@db/app",
        "database_auto_create": False,
        "rate_limit_backend": "memory",
        "app_replica_count": 1,
        "audit_hash_key": "audit-secret",
    }
    values.update(overrides)
    return Settings(**values)


def _staging(**overrides) -> Settings:
    values = {
        "environment": "staging",
        "api_bearer_token": "service-secret",
        "gateway_assertion_required": True,
        "allow_unsigned_identity_headers": False,
        "gateway_assertion_issuer": "https://gateway-staging.example.com",
        "gateway_assertion_audience": "face-api-staging",
        "gateway_allowed_tenants": "tenant-001",
        "gateway_jwks_path": "gateway-staging-public.jwks.json",
        "biometric_encryption_key": Fernet.generate_key().decode("ascii"),
        "device_reset_token": "admin-secret",
        "audit_hash_key": "audit-secret",
        "cors_allowed_origins": "https://ess-staging.example",
        "enable_api_docs": False,
        "detector_provider": "yunet",
        "recognizer_provider": "arcface_onnx",
        "require_calibration": True,
        "liveness_required": False,
        "liveness_provider": "disabled",
        "device_proof_required": True,
        "allow_legacy_device_id_only": False,
        "database_url": "postgresql+psycopg://user:pass@db/staging",
        "database_auto_create": False,
        "rate_limit_backend": "redis",
        "redis_url": "redis://redis:6379/0",
        "app_replica_count": 1,
        "allow_embedding_return": False,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize("override,expected", [
    ({"api_bearer_token": None}, "API_BEARER_TOKEN"),
    ({"detector_provider": "mock"}, "YuNet and ArcFace"),
    ({"cors_allowed_origins": "*"}, "CORS_ALLOWED_ORIGINS"),
    ({"enable_api_docs": True}, "documentation"),
    ({"liveness_required": True}, "liveness"),
    ({"device_proof_required": False}, "device proof"),
    ({"database_url": "sqlite:///staging.sqlite3"}, "PostgreSQL"),
    ({"database_auto_create": True}, "DATABASE_AUTO_CREATE"),
    ({"rate_limit_backend": "memory"}, "Redis"),
    ({"allow_embedding_return": True}, "Embedding return"),
])
def test_staging_unsafe_configuration_fails_closed(override, expected) -> None:
    with pytest.raises(RuntimeError, match=expected):
        validate_deployment_settings(_staging(**override))


def test_valid_staging_settings_pass() -> None:
    validate_deployment_settings(_staging())


@pytest.mark.parametrize("override,expected", [
    ({"api_bearer_token": None}, "API_BEARER_TOKEN"),
    ({"biometric_encryption_key": None}, "BIOMETRIC_ENCRYPTION_KEY"),
    ({"device_reset_token": None}, "DEVICE_RESET_TOKEN"),
    ({"detector_provider": "mock"}, "Mock face providers"),
    ({"recognizer_provider": "mock"}, "Mock face providers"),
    ({"cors_allowed_origins": "*"}, "CORS_ALLOWED_ORIGINS"),
    ({"enable_api_docs": True}, "documentation"),
    ({"require_calibration": False}, "REQUIRE_CALIBRATION"),
    ({"liveness_required": False}, "LIVENESS_REQUIRED"),
    ({"liveness_provider": "mock"}, "real liveness provider"),
    ({"liveness_provider": "disabled"}, "real liveness provider"),
    ({"allow_legacy_single_image_verification": True}, "Legacy single-image"),
    ({"device_proof_required": False}, "DEVICE_PROOF_REQUIRED"),
    ({"allow_legacy_device_id_only": True}, "Legacy device-ID-only"),
    ({"database_url": None}, "DATABASE_URL"),
    ({"database_url": "sqlite:///data.sqlite3"}, "SQLite"),
    ({"database_auto_create": True}, "DATABASE_AUTO_CREATE"),
    ({"rate_limit_backend": "invalid"}, "RATE_LIMIT_BACKEND"),
    ({"rate_limit_backend": "redis", "redis_url": None}, "REDIS_URL"),
    ({"app_replica_count": 2}, "Redis rate limiting"),
    ({"audit_hash_key": None}, "AUDIT_HASH_KEY"),
])
def test_production_unsafe_configuration_fails_closed(override, expected) -> None:
    with pytest.raises(RuntimeError, match=expected):
        validate_deployment_settings(_secure(**override))


def _deployment_profile(status: str = "approved") -> dict:
    return {
        "schema_version": 2,
        "calibration_version": "deployment-v1",
        "model_provider": "arcface_onnx",
        "recognizer_provider": "arcface_onnx",
        "model_sha256": Settings().arcface_sha256,
        "detector_version": "yunet_2023mar_opencv",
        "preprocessing_version": "align112_rgb_v1",
        "alignment_version": "arcface_5point_112_v1",
        "dataset_version": "approved-pseudonymous-v1",
        "split_strategy": "identity_disjoint_calibration_test",
        "target_fmr": 0.01,
        "threshold": 0.4,
        "threshold_confidence_interval_95": [0.38, 0.42],
        "pair_counts": {"genuine": 10, "impostor": 100},
        "created_at": "2026-01-01T00:00:00+00:00",
        "approval_status": status,
        "real_probability": False,
        "operating_point": "deployment_fmr_1e-2",
        "score_calibration": {"method": "none", "real_probability": False},
        "validation_metadata": {
            "test_pair_counts": {"genuine": 10, "impostor": 100},
            "fnmr_at_threshold": 0.1,
            "failure_to_acquire_rate": 0.05,
            "latency_ms": {"p95": 500},
        },
    }


def test_unapproved_or_mismatched_deployment_calibration_is_rejected(tmp_path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(_deployment_profile("pending")), encoding="utf-8")
    settings = _secure(
        require_approved_deployment_calibration=True,
        approved_calibration_profile_path=str(path),
        deployment_min_genuine_pairs=10,
        deployment_min_impostor_pairs=100,
        deployment_target_fmr=0.01,
        deployment_max_fnmr_at_target_fmr=0.2,
        deployment_max_failure_to_acquire_rate=0.1,
        deployment_max_p95_latency_ms=1000,
    )
    with pytest.raises(CalibrationProfileError, match="not approved"):
        validate_deployment_settings(settings)
    profile = _deployment_profile()
    profile["model_sha256"] = "0" * 64
    path.write_text(json.dumps(profile), encoding="utf-8")
    with pytest.raises(CalibrationProfileError, match="checksum mismatch"):
        validate_deployment_settings(settings)


def test_approved_deployment_calibration_passes_configured_gates(tmp_path) -> None:
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(_deployment_profile()), encoding="utf-8")
    validate_deployment_settings(_secure(
        require_approved_deployment_calibration=True,
        approved_calibration_profile_path=str(path),
        deployment_min_genuine_pairs=10,
        deployment_min_impostor_pairs=100,
        deployment_target_fmr=0.01,
        deployment_max_fnmr_at_target_fmr=0.2,
        deployment_max_failure_to_acquire_rate=0.1,
        deployment_max_p95_latency_ms=1000,
    ))
