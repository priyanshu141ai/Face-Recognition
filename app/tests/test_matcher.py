from app.services.matcher import FaceMatcher


def test_cosine_similarity_normalizes_embeddings() -> None:
    matcher = FaceMatcher()
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert matcher.cosine_similarity(a, b) == 0.0
