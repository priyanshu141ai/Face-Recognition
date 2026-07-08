import hashlib
import numpy as np

from app.services.recognizer_base import BaseFaceRecognizer


class MockFaceRecognizer(BaseFaceRecognizer):
    def embed(self, aligned_face: np.ndarray) -> np.ndarray:
        digest = hashlib.sha256(aligned_face.tobytes()).hexdigest()
        values = [int(digest[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]
        return np.asarray(values, dtype=np.float32)
