import numpy as np
import pytest

from app.core.errors import FaceAlignmentError
from app.services.alignment import FaceAligner


def test_alignment_returns_112_bgr_image() -> None:
    image = np.zeros((160, 160, 3), dtype=np.uint8)
    landmarks = [[50, 60], [100, 60], [75, 85], [55, 115], [95, 115]]
    aligned = FaceAligner().align_face_112(image, landmarks)
    assert aligned.shape == (112, 112, 3)
    assert aligned.dtype == np.uint8


def test_alignment_rejects_wrong_landmark_count() -> None:
    with pytest.raises(FaceAlignmentError):
        FaceAligner().align_face_112(np.zeros((160, 160, 3), dtype=np.uint8), [[1, 2]])
