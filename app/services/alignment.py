import cv2
import numpy as np

from app.core.errors import FaceAlignmentError


class FaceAligner:
    def __init__(self) -> None:
        self.destination_points = np.array(
            [
                [38.2946, 51.6963],
                [73.5318, 51.5014],
                [56.0252, 71.7366],
                [41.5493, 92.3655],
                [70.7299, 92.2041],
            ],
            dtype=np.float32,
        )

    def align_face_112(self, image_bgr: np.ndarray, landmarks5: list[list[float]]) -> np.ndarray:
        if len(landmarks5) != 5:
            raise FaceAlignmentError("face_alignment_failed")

        src = np.array(landmarks5, dtype=np.float32).reshape(5, 2)
        transform, _ = cv2.estimateAffinePartial2D(src, self.destination_points)
        if transform is None:
            raise FaceAlignmentError("face_alignment_failed")

        aligned = cv2.warpAffine(image_bgr, transform, (112, 112))
        if aligned.shape != (112, 112, 3):
            aligned = cv2.resize(aligned, (112, 112), interpolation=cv2.INTER_AREA)
        return aligned
