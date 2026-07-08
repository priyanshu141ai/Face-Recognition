import numpy as np
import pytest

from app.services.matcher import FaceMatcher


def test_threshold_is_inclusive() -> None:
    matcher = FaceMatcher(threshold=0.40)
    assert matcher.decide(0.40) == "match"
    assert matcher.decide(0.3999) == "non_match"


def test_cosine_similarity_normalizes_inputs() -> None:
    matcher = FaceMatcher()
    assert matcher.cosine_similarity(np.array([2.0, 0.0]), np.array([10.0, 0.0])) == pytest.approx(1.0)
    assert matcher.cosine_similarity(np.array([1.0, 0.0]), np.array([0.0, 1.0])) == pytest.approx(0.0)


def test_zero_vector_similarity_is_safe() -> None:
    matcher = FaceMatcher()
    assert matcher.cosine_similarity(np.zeros(4), np.ones(4)) == pytest.approx(0.0)
