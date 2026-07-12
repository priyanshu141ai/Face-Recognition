import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.benchmark.threshold_calibration import evaluate_threshold, fit_balanced_platt, select_threshold_at_fmr, sigmoid_scores


def _arrays(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    return frame["similarity_cosine"].to_numpy(float), frame["label"].to_numpy(int)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit per-model thresholds with identity-fold cross-validation")
    parser.add_argument("--results", required=True)
    parser.add_argument("--dataset", default="benchmark_data/lfw_phase5")
    parser.add_argument("--output", default="calibration")
    parser.add_argument("--target-fmr", type=float, default=1e-3)
    args = parser.parse_args()
    results_path, dataset, output = Path(args.results), Path(args.dataset), Path(args.output)
    frame = pd.read_csv(results_path)
    required = {"model_name", "label", "similarity_cosine", "error_code", "model_sha256", "dataset_sha256", "fold_a", "fold_b"}
    if missing := required - set(frame.columns):
        raise SystemExit(f"Results missing columns: {sorted(missing)}")
    manifest = json.loads((dataset / "manifest.json").read_text(encoding="utf-8"))
    if not manifest.get("identity_disjoint") or manifest.get("protocol") != "identity_kfold_cross_validation":
        raise SystemExit("Dataset manifest is not identity-fold cross-validation")
    pairs_sha = hashlib.sha256((dataset / "pairs.csv").read_bytes()).hexdigest()
    if set(frame["dataset_sha256"].dropna()) != {pairs_sha}:
        raise SystemExit("Results do not match the dataset fingerprint")
    output.mkdir(parents=True, exist_ok=True)

    for model_name, model_rows in frame.groupby("model_name"):
        valid = model_rows[model_rows["error_code"].isna() & model_rows["similarity_cosine"].notna()].copy()
        folds, oof_rows = int(manifest["folds"]), []
        fold_reports = []
        for fold in range(folds):
            train = valid[(valid["fold_a"] != fold) & (valid["fold_b"] != fold)]
            test = valid[(valid["fold_a"] == fold) & (valid["fold_b"] == fold)]
            train_scores, train_labels = _arrays(train)
            test_scores, test_labels = _arrays(test)
            threshold = select_threshold_at_fmr(train_scores, train_labels, args.target_fmr)
            coefficient, intercept = fit_balanced_platt(train_scores, train_labels)
            metrics = evaluate_threshold(test_scores, test_labels, threshold)
            metrics.update({"fold": fold, "threshold": threshold, "auc": float(roc_auc_score(test_labels, test_scores))})
            fold_reports.append(metrics)
            selected = test[["label", "similarity_cosine"]].copy()
            selected["threshold"] = threshold
            selected["calibrated_score"] = sigmoid_scores(test_scores, coefficient, intercept)
            oof_rows.append(selected)

        oof = pd.concat(oof_rows, ignore_index=True)
        oof_labels = oof["label"].to_numpy(int)
        oof_predictions = oof["similarity_cosine"].to_numpy(float) >= oof["threshold"].to_numpy(float)
        genuine = oof_labels == 1
        impostor = oof_labels == 0
        oof_metrics = {
            "genuine_pairs": int(genuine.sum()), "impostor_pairs": int(impostor.sum()),
            "fmr": float(oof_predictions[impostor].mean()),
            "fnmr": float((~oof_predictions[genuine]).mean()),
            "auc": float(roc_auc_score(oof_labels, oof["similarity_cosine"])),
            "balanced_brier": float(0.5 * np.mean((oof.loc[genuine, "calibrated_score"] - 1) ** 2) + 0.5 * np.mean(oof.loc[impostor, "calibrated_score"] ** 2)),
        }
        all_scores, all_labels = _arrays(valid)
        final_threshold = select_threshold_at_fmr(all_scores, all_labels, args.target_fmr)
        coefficient, intercept = fit_balanced_platt(all_scores, all_labels)
        artifact = {
            "schema_version": 1, "calibration_version": "identity_5fold_platt_v1",
            "created_at": datetime.now(timezone.utc).isoformat(), "model_provider": model_name,
            "model_sha256": str(model_rows["model_sha256"].dropna().iloc[0]), "dataset_sha256": pairs_sha,
            "split_seed": manifest["seed"], "folds": folds, "target_fmr": args.target_fmr,
            "threshold": final_threshold, "operating_point": f"identity_5fold_fmr_{args.target_fmr:.0e}",
            "score_calibration": {"method": "balanced_platt_logistic", "coefficient": coefficient, "intercept": intercept, "real_probability": False},
            "cross_validation": {"aggregate": oof_metrics, "folds": fold_reports},
            "final_fit_metrics": evaluate_threshold(all_scores, all_labels, final_threshold),
            "limitations": ["LFW is a research dataset", "pair trials sharing identities are correlated", "calibrated score is not a real-world identity probability"],
        }
        path = output / f"{model_name}.json"
        path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
        print(f"{model_name}: threshold={final_threshold:.6f} cv_fmr={oof_metrics['fmr']:.6f} cv_fnmr={oof_metrics['fnmr']:.6f} -> {path}")


if __name__ == "__main__":
    main()
