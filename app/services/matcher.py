import numpy as np


class FaceMatcher:
    def __init__(self, threshold: float = 0.40) -> None:
        self.threshold = threshold

    def _normalize(self, embedding: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm

    def cosine_similarity(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        a = self._normalize(np.asarray(emb_a, dtype=np.float32))
        b = self._normalize(np.asarray(emb_b, dtype=np.float32))
        return float(np.dot(a, b))

    def decide(self, similarity: float) -> str:
        return "match" if similarity >= self.threshold else "non_match"
