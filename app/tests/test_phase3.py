import os

import numpy as np
import pytest

os.environ.setdefault("DETECTOR_PROVIDER", "mock")
os.environ.setdefault("RECOGNIZER_PROVIDER", "mock")

from app.api.v1.routes_models import current_models
from app.core.config import get_settings
from app.models.arcface_onnx_recognizer import ArcFaceOnnxRecognizer
from app.models.mock_recognizer import MockFaceRecognizer
from app.services.alignment import FaceAligner
from app.services.matcher import FaceMatcher, l2_normalize
from app.services.pipeline import FaceVerificationPipeline


def test_l2_normalize_returns_unit_norm() -> None:
    vector = np.array([3.0, 4.0], dtype=np.float32)
    normalized = l2_normalize(vector)
    assert np.isclose(np.linalg.norm(normalized), 1.0)


def test_cosine_similarity_of_same_vector_is_close_to_one() -> None:
    matcher = FaceMatcher(threshold=0.4)
    similarity = matcher.cosine_similarity(np.array([1.0, 2.0, 3.0], dtype=np.float32), np.array([1.0, 2.0, 3.0], dtype=np.float32))
    assert np.isclose(similarity, 1.0)


def test_cosine_similarity_of_different_vectors_behaves_correctly() -> None:
    matcher = FaceMatcher(threshold=0.4)
    similarity = matcher.cosine_similarity(np.array([1.0, 0.0], dtype=np.float32), np.array([0.0, 1.0], dtype=np.float32))
    assert similarity == pytest.approx(0.0, abs=1e-6)


def test_alignment_returns_112x112x3_crop_using_fake_landmarks() -> None:
    aligner = FaceAligner()
    image = np.zeros((64, 64, 3), dtype=np.uint8)
    landmarks = [
        [10.0, 10.0],
        [30.0, 10.0],
        [20.0, 25.0],
        [10.0, 40.0],
        [30.0, 40.0],
    ]
    aligned = aligner.align_face_112(image, landmarks)
    assert aligned.shape == (112, 112, 3)


def test_arcface_recognizer_raises_clean_error_if_model_file_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ARCFACE_MODEL_PATH", str(tmp_path / "missing.onnx"))
    with pytest.raises(Exception, match="ArcFace ONNX model not found"):
        ArcFaceOnnxRecognizer()


def test_provider_selection_uses_mock_when_provider_is_mock(monkeypatch) -> None:
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "mock")
    pipeline = FaceVerificationPipeline()
    assert isinstance(pipeline._get_recognizer(), MockFaceRecognizer)


def test_models_current_returns_recognizer_metadata() -> None:
    result = current_models()
    assert "recognizer" in result
    assert result["recognizer"]["name"] in {"arcface_r100_onnx", "mock_arcface_adapter_v1"}


@pytest.mark.integration
def test_arcface_inference_is_skipped_without_model_file() -> None:
    if not os.path.exists(get_settings().arcface_model_path):
        pytest.skip("ArcFace ONNX model not available")
    recognizer = ArcFaceOnnxRecognizer()
    image = np.zeros((112, 112, 3), dtype=np.uint8)
    embedding = recognizer.embed(image)
    assert embedding.shape[0] == get_settings().arcface_embedding_dim
