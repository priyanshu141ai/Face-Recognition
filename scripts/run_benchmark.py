import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.benchmark.report import generate_benchmark_report
from app.benchmark.runner import BenchmarkRunner
from app.core.config import get_settings
from app.benchmark.model_artifacts import evaluate_benchmark_readiness, inspect_onnx_model


def _resolve_models_to_run(models: list[str], skip_missing_models: bool, settings) -> list[str]:
    def configured_path(value: str) -> Path:
        path = Path(value)
        return path if path.is_absolute() else PROJECT_ROOT / path

    model_paths = {
        "arcface_onnx": configured_path(settings.arcface_model_path),
        "mobilefacenet_onnx": configured_path(settings.mobilefacenet_model_path),
        "insightface_buffalo_l": None,
    }
    selected: list[str] = []
    for model in models:
        if model in {"mock", "arcface_onnx", "mobilefacenet_onnx", "insightface_buffalo_l"}:
            if model in {"arcface_onnx", "mobilefacenet_onnx"} and inspect_onnx_model(model_paths[model]).get("status") != "LOADED":
                if skip_missing_models:
                    print(f"Skipping {model}: missing {model_paths[model]}")
                    continue
                raise SystemExit(f"Missing required model artifact for {model}: {model_paths[model]}")
            if model == "insightface_buffalo_l":
                try:
                    import importlib.util
                    if importlib.util.find_spec("insightface") is None:
                        if skip_missing_models:
                            print("Skipping insightface_buffalo_l: optional InsightFace package is not installed")
                            continue
                        raise SystemExit("InsightFace is not installed")
                except Exception:
                    if skip_missing_models:
                        print("Skipping insightface_buffalo_l: optional InsightFace package is not installed")
                        continue
                    raise SystemExit("InsightFace is not installed")
            selected.append(model)
        else:
            selected.append(model)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--threshold", type=float, default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--skip-missing-models", action="store_true")
    parser.add_argument("--detector", choices=["yunet", "mock"], default="yunet")
    parser.add_argument("--allow-mock", action="store_true", help="Required acknowledgement for non-scientific mock runs")
    parser.add_argument("--dataset-name", default=None)
    args = parser.parse_args()

    settings = get_settings()
    output_dir = Path(args.output or settings.benchmark_output_dir)
    readiness = evaluate_benchmark_readiness(args.dataset)
    if not readiness["ok"]:
        raise SystemExit("Dataset is not benchmark-ready: " + "; ".join(readiness["errors"]))
    for warning in readiness.get("warnings", []):
        print(f"WARNING: {warning}")
    yunet_path = Path(settings.yunet_model_path)
    yunet_path = yunet_path if yunet_path.is_absolute() else PROJECT_ROOT / yunet_path
    if args.detector == "yunet" and inspect_onnx_model(yunet_path).get("status") != "LOADED":
        raise SystemExit(f"YuNet artifact is missing or invalid: {yunet_path}")

    models_to_run = _resolve_models_to_run(args.models, skip_missing_models=args.skip_missing_models, settings=settings)
    if not models_to_run:
        print("No runnable models remain after model validation")
        output_dir.mkdir(parents=True, exist_ok=True)
        generate_benchmark_report([], output_dir=output_dir, dataset_name=args.dataset_name or Path(args.dataset).name)
        print("Benchmark complete")
        return

    runner = BenchmarkRunner(
        models=models_to_run,
        dataset_path=args.dataset,
        threshold=args.threshold,
        detector_provider=args.detector,
        allow_mock=args.allow_mock,
    )
    results = runner.run()
    paths = generate_benchmark_report(results, output_dir=output_dir, dataset_name=args.dataset_name or Path(args.dataset).name)

    print("Benchmark complete")
    for path in paths.values():
        print(path)


if __name__ == "__main__":
    main()
