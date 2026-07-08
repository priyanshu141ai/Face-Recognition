from __future__ import annotations

import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from typing import Any

from app.benchmark.metrics import compute_benchmark_metrics


def generate_benchmark_report(results: list[dict[str, Any]], output_dir: str | Path, dataset_name: str = "benchmark") -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = pd.DataFrame(results)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = output_dir / f"results_{dataset_name}_{stamp}.csv"
    json_path = output_dir / f"summary_{dataset_name}_{stamp}.json"
    md_path = output_dir / f"report_{dataset_name}_{stamp}.md"

    frame.to_csv(csv_path, index=False)

    genuine_pairs = int((frame["label"] == 1).sum()) if "label" in frame.columns else 0
    impostor_pairs = int((frame["label"] == 0).sum()) if "label" in frame.columns else 0
    summary: dict[str, Any] = {
        "dataset_name": dataset_name,
        "rows": len(frame),
        "genuine_pairs": genuine_pairs,
        "impostor_pairs": impostor_pairs,
        "warning": "This benchmark is only valid for the dataset used in this run.",
    }
    summary["models"] = []
    model_names = sorted(frame["model_name"].dropna().unique().tolist()) if "model_name" in frame.columns else []
    for model_name in model_names:
        subset = frame[frame["model_name"] == model_name]
        metrics = compute_benchmark_metrics(subset.to_dict(orient="records"), threshold=0.40)
        summary["models"].append({
            "model_name": model_name,
            "rows": len(subset),
            "auc": metrics["auc"],
            "eer": metrics["eer"],
            "fnmr_at_fmr_1e-3": metrics["fnmr_at_fmr_1e-3"],
            "fnmr_at_fmr_1e-4": metrics["fnmr_at_fmr_1e-4"],
            "fnmr_at_fmr_1e-5": metrics["fnmr_at_fmr_1e-5"],
            "avg_latency_ms": float(subset["total_ms"].mean()) if not subset.empty else 0.0,
            "p50_latency_ms": float(subset["total_ms"].quantile(0.5)) if not subset.empty else 0.0,
            "p95_latency_ms": float(subset["total_ms"].quantile(0.95)) if not subset.empty else 0.0,
            "failures": int(subset["error_code"].notna().sum()),
            "recommendation": "review" if metrics["auc"] < 0.8 else "keep",
            "detector_used": _first_value(subset, "detector_used", "unknown"),
            "alignment_used": _first_value(subset, "alignment_used", "5-point similarity transform to 112x112"),
            "recognizer_used": _first_value(subset, "recognizer_used", model_name),
            "preprocessing_version": _first_value(subset, "preprocessing_version", "align112_rgb_v1"),
            "embedding_dimension": _first_value(subset, "embedding_dim", None),
            "threshold_used": float(frame["threshold"].mean()) if (not frame.empty and "threshold" in frame.columns) else 0.4,
            "license_note": _first_value(subset, "license_note", "weights may have separate licenses"),
        })

    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    markdown_lines = [
        f"# Benchmark Report: {dataset_name}",
        "",
        f"- Rows: {len(frame)}",
        f"- Genuine pairs: {genuine_pairs}",
        f"- Impostor pairs: {impostor_pairs}",
        f"- Models: {', '.join(model_names)}",
        "",
        "## Benchmark note",
        "",
        "Important: This benchmark report is only valid for the dataset used in this run. Do not treat these numbers as production truth unless the dataset is representative, identity-disjoint, and large enough for the target FMR.",
        "",
        "## Model comparison",
        "",
        "| model | AUC | EER | FNMR@1e-3 | FNMR@1e-4 | FNMR@1e-5 | Avg latency ms | Failures |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in summary["models"]:
        markdown_lines.append(
            f"| {item['model_name']} | {item['auc']:.3f} | {item['eer']:.3f} | {item['fnmr_at_fmr_1e-3']:.3f} | {item['fnmr_at_fmr_1e-4']:.3f} | {item['fnmr_at_fmr_1e-5']:.3f} | {item['avg_latency_ms']:.2f} | {item['failures']} |"
        )
    markdown_lines.extend([
        "",
        "## Model metadata",
        "",
        "| model | detector | alignment | recognizer | preprocessing | embedding dim | threshold | license note |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for item in summary["models"]:
        markdown_lines.append(
            f"| {item['model_name']} | {item['detector_used']} | {item['alignment_used']} | {item['recognizer_used']} | {item['preprocessing_version']} | {item['embedding_dimension']} | {item['threshold_used']:.3f} | {item['license_note']} |"
        )
    markdown_lines.extend([
        "",
        "## Recommendation",
        "",
        "- ArcFace remains the default production recognizer for Phase 4.",
    ])
    md_path.write_text("\n".join(markdown_lines), encoding="utf-8")

    return {"csv": csv_path, "json": json_path, "markdown": md_path}


def _first_value(frame: pd.DataFrame, column: str, default: Any) -> Any:
    if column not in frame.columns or frame.empty:
        return default
    values = frame[column].dropna()
    value = values.iloc[0] if not values.empty else default
    return value.item() if hasattr(value, "item") else value
