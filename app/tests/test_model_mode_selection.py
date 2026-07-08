import pytest
from fastapi.testclient import TestClient

from app.core.errors import DetectorProviderError, RecognizerProviderError
from app.main import app
from app.models.mock_detector import MockFaceDetector
from app.models.mock_recognizer import MockFaceRecognizer
from app.services.pipeline import FaceVerificationPipeline


def test_pipeline_uses_mock_providers(monkeypatch) -> None:
    monkeypatch.setenv("DETECTOR_PROVIDER", "mock")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "mock")
    pipeline = FaceVerificationPipeline()
    assert isinstance(pipeline._get_detector(), MockFaceDetector)
    assert isinstance(pipeline._get_recognizer(), MockFaceRecognizer)


def test_invalid_detector_provider_raises(monkeypatch) -> None:
    monkeypatch.setenv("DETECTOR_PROVIDER", "invalid")
    with pytest.raises(DetectorProviderError):
        FaceVerificationPipeline()._get_detector()


def test_invalid_recognizer_provider_raises(monkeypatch) -> None:
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "invalid")
    with pytest.raises(RecognizerProviderError):
        FaceVerificationPipeline()._get_recognizer()


def test_models_current_reports_real_names_without_loading_models(monkeypatch) -> None:
    monkeypatch.setenv("DETECTOR_PROVIDER", "yunet")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "arcface_onnx")
    data = TestClient(app).get("/v1/models/current").json()
    assert data["detector"]["name"] == "yunet_2023mar_opencv"
    assert data["recognizer"]["name"] == "arcface_r100_onnx"
    assert data["recognizer"]["embedding_dim"] == 512
