import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings, validate_deployment_settings
from app.services.pipeline import get_face_verification_pipeline


def _production_settings(**overrides) -> Settings:
    values = {
        "environment": "production",
        "api_bearer_token": "service-secret",
        "biometric_encryption_key": Fernet.generate_key().decode("ascii"),
        "device_reset_token": "reset-secret",
        "cors_allowed_origins": "https://ess.example.com",
        "detector_provider": "yunet",
        "recognizer_provider": "arcface_onnx",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_requires_all_secrets() -> None:
    with pytest.raises(RuntimeError, match="API_BEARER_TOKEN"):
        validate_deployment_settings(_production_settings(api_bearer_token=None))


def test_production_rejects_mock_providers() -> None:
    with pytest.raises(RuntimeError, match="Mock face providers"):
        validate_deployment_settings(_production_settings(detector_provider="mock"))


def test_production_rejects_wildcard_cors() -> None:
    with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS"):
        validate_deployment_settings(_production_settings(cors_allowed_origins="*"))


def test_valid_production_settings_pass() -> None:
    validate_deployment_settings(_production_settings())


def test_pipeline_is_reused_for_the_same_settings(monkeypatch) -> None:
    monkeypatch.setenv("DETECTOR_PROVIDER", "mock")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "mock")
    assert get_face_verification_pipeline() is get_face_verification_pipeline()
