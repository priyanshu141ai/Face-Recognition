import numpy as np


def l2_normalize(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float32)
    norm = np.linalg.norm(x)
    if norm == 0.0:
        return x
    return x / norm


class FaceMatcher:
    def __init__(self, threshold: float = 0.40) -> None:
        self.threshold = threshold

    def cosine_similarity(self, emb_a: np.ndarray, emb_b: np.ndarray) -> float:
        a = l2_normalize(np.asarray(emb_a, dtype=np.float32))
        b = l2_normalize(np.asarray(emb_b, dtype=np.float32))
        return float(np.dot(a, b))

    def decide(self, similarity: float) -> str:
        return "match" if similarity >= self.threshold else "non_match"
