import pytest

from app.core.errors import FaceQualityError
from app.models.mock_detector import MockFaceDetector
from app.schemas.common import QualityPolicy
from app.schemas.face import FaceDetectionSchema
from app.services.pipeline import FaceVerificationPipeline


def _face(confidence: float = 0.99) -> FaceDetectionSchema:
    return FaceDetectionSchema(
        bbox_xywh=[10.0, 10.0, 80.0, 80.0],
        landmarks5=[[20.0, 30.0], [40.0, 30.0], [30.0, 45.0], [22.0, 60.0], [38.0, 60.0]],
        detection_confidence=confidence,
    )


def test_mock_detector_returns_detection_schema() -> None:
    faces = MockFaceDetector().detect(b"image-bytes")
    assert len(faces) == 1
    assert len(faces[0].bbox_xywh) == 4
    assert len(faces[0].landmarks5) == 5
    assert 0.0 <= faces[0].detection_confidence <= 1.0


def test_quality_rejects_no_face_and_multiple_faces() -> None:
    pipeline = FaceVerificationPipeline()
    with pytest.raises(FaceQualityError, match="no face"):
        pipeline._validate_quality([], QualityPolicy(), "image")
    with pytest.raises(FaceQualityError, match="multiple faces"):
        pipeline._validate_quality([_face(), _face()], QualityPolicy(), "image")


def test_quality_rejects_low_confidence() -> None:
    with pytest.raises(FaceQualityError, match="quality"):
        FaceVerificationPipeline()._validate_quality([_face(0.1)], QualityPolicy(min_detection_confidence=0.85), "image")
