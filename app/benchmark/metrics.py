from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import auc, roc_curve


def _scores_and_labels(results: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray]:
    valid_results = [
        item
        for item in results
        if item.get("similarity_cosine") is not None and item.get("label") is not None
    ]
    if not valid_results:
        return np.array([], dtype=np.float32), np.array([], dtype=np.int32)

    scores = np.array([float(item["similarity_cosine"]) for item in valid_results], dtype=np.float32)
    labels = np.array([int(item["label"]) for item in valid_results], dtype=np.int32)
    return scores, labels


def compute_benchmark_metrics(results: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    scores, labels = _scores_and_labels(results)
    preds = (scores >= threshold).astype(int)

    if len(scores) == 0 or len(np.unique(labels)) != 2:
        fpr = []
        tpr = []
        roc_auc = 0.0
        genuine_scores = scores[labels == 1]
        impostor_scores = scores[labels == 0]
    else:
        fpr, tpr, _ = roc_curve(labels, scores, pos_label=1)
        roc_auc = float(auc(fpr, tpr)) if len(np.unique(labels)) == 2 else 0.0
        genuine_scores = scores[labels == 1]
        impostor_scores = scores[labels == 0]

    if len(genuine_scores) == 0 or len(impostor_scores) == 0:
        eer = 0.0
        fmr_at_threshold = 0.0
        fnmr_at_threshold = 0.0
        fnmr_at_fmr_1e3 = 0.0
        fnmr_at_fmr_1e4 = 0.0
        fnmr_at_fmr_1e5 = 0.0
        best_threshold_by_eer = threshold
    else:
        best_gap = float("inf")
        eer = 1.0
        best_threshold_by_eer = threshold
        candidates = np.unique(np.concatenate([scores, np.array([scores.min() - 1e-6, scores.max() + 1e-6], dtype=np.float32)]))
        for candidate in candidates:
            fmr = float(np.mean(impostor_scores >= candidate))
            fnmr = float(np.mean(genuine_scores < candidate))
            gap = abs(fmr - fnmr)
            if gap < best_gap:
                best_gap = gap
                eer = float((fmr + fnmr) / 2.0)
                best_threshold_by_eer = float(candidate)
        fmr_at_threshold = float(np.mean(impostor_scores >= threshold))
        fnmr_at_threshold = float(np.mean(genuine_scores < threshold))

        def fnmr_at_target_fmr(target_fmr: float) -> float:
            target_threshold = float(np.quantile(impostor_scores, max(0.0, 1.0 - target_fmr)))
            return float(np.mean(genuine_scores < target_threshold))

        fnmr_at_fmr_1e3 = fnmr_at_target_fmr(1e-3)
        fnmr_at_fmr_1e4 = fnmr_at_target_fmr(1e-4)
        fnmr_at_fmr_1e5 = fnmr_at_target_fmr(1e-5)

    return {
        "auc": roc_auc,
        "eer": eer,
        "fmr_at_threshold": fmr_at_threshold,
        "fnmr_at_threshold": fnmr_at_threshold,
        "fnmr_at_fmr_1e-3": fnmr_at_fmr_1e3,
        "fnmr_at_fmr_1e-4": fnmr_at_fmr_1e4,
        "fnmr_at_fmr_1e-5": fnmr_at_fmr_1e5,
        "genuine_scores": genuine_scores.tolist(),
        "impostor_scores": impostor_scores.tolist(),
        "threshold": threshold,
        "predictions": preds.tolist(),
        "labels": labels.tolist(),
        "fpr": fpr.tolist() if hasattr(fpr, "tolist") else list(fpr),
        "tpr": tpr.tolist() if hasattr(tpr, "tolist") else list(tpr),
        "best_threshold_by_eer": best_threshold_by_eer,
    }
