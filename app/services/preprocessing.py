import numpy as np


class Preprocessor:
    def align_face(self, image: np.ndarray, detection: object) -> np.ndarray:
        return np.zeros((112, 112, 3), dtype=np.uint8)
