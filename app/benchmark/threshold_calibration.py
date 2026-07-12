from __future__ import annotations

from math import ceil, floor
from typing import Any

import numpy as np
from scipy.stats import beta
from sklearn.linear_model import LogisticRegression


def select_threshold_at_fmr(scores: np.ndarray, labels: np.ndarray, target_fmr: float) -> float:
    impostor = np.asarray(scores, dtype=np.float64)[np.asarray(labels) == 0]
    if not 0 < target_fmr < 1:
        raise ValueError("target_fmr must be between 0 and 1")
    if len(impostor) < ceil(1 / target_fmr):
        raise ValueError(f"need at least {ceil(1 / target_fmr)} impostor pairs")
    allowed = floor(target_fmr * len(impostor))
    descending = np.sort(impostor)[::-1]
    return float(np.nextafter(descending[allowed], np.inf))


def fit_balanced_platt(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int32)
    counts = np.bincount(labels, minlength=2)
    if np.any(counts == 0):
        raise ValueError("both genuine and impostor scores are required")
    weights = np.where(labels == 1, 0.5 / counts[1], 0.5 / counts[0])
    model = LogisticRegression(C=1.0, solver="lbfgs", random_state=0)
    model.fit(scores.reshape(-1, 1), labels, sample_weight=weights * len(labels))
    return float(model.coef_[0, 0]), float(model.intercept_[0])


def sigmoid_scores(scores: np.ndarray, coefficient: float, intercept: float) -> np.ndarray:
    logits = np.clip(coefficient * np.asarray(scores, dtype=np.float64) + intercept, -60, 60)
    return 1.0 / (1.0 + np.exp(-logits))


def binomial_interval(errors: int, trials: int, confidence: float = 0.95) -> list[float] | None:
    if trials <= 0:
        return None
    alpha = 1.0 - confidence
    lower = 0.0 if errors == 0 else float(beta.ppf(alpha / 2, errors, trials - errors + 1))
    upper = 1.0 if errors == trials else float(beta.ppf(1 - alpha / 2, errors + 1, trials - errors))
    return [lower, upper]


def evaluate_threshold(scores: np.ndarray, labels: np.ndarray, threshold: float) -> dict[str, Any]:
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int32)
    genuine, impostor = scores[labels == 1], scores[labels == 0]
    false_matches = int(np.sum(impostor >= threshold))
    false_non_matches = int(np.sum(genuine < threshold))
    return {
        "genuine_pairs": int(len(genuine)),
        "impostor_pairs": int(len(impostor)),
        "false_matches": false_matches,
        "false_non_matches": false_non_matches,
        "fmr": false_matches / len(impostor) if len(impostor) else None,
        "fnmr": false_non_matches / len(genuine) if len(genuine) else None,
        "fmr_95ci": binomial_interval(false_matches, len(impostor)),
        "fnmr_95ci": binomial_interval(false_non_matches, len(genuine)),
    }
