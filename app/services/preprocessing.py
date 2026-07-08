import numpy as np

from app.core.errors import FaceAlignmentError
from app.services.alignment import FaceAligner


class Preprocessor:
    def __init__(self) -> None:
        self.aligner = FaceAligner()

    def align_face(self, image: np.ndarray, detection: object) -> np.ndarray:
        try:
            return self.aligner.align_face_112(image, detection.landmarks5)
        except Exception as exc:
            raise FaceAlignmentError("face_alignment_failed") from exc
