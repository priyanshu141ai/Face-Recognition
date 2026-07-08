import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.benchmark.report import generate_benchmark_report
from app.benchmark.runner import BenchmarkRunner
from app.core.config import get_settings
from app.benchmark.model_artifacts import validate_model_artifacts


def _resolve_models_to_run(models: list[str], skip_missing_models: bool) -> list[str]:
    model_paths = {
        "arcface_onnx": PROJECT_ROOT / "models" / "face-recognition-resnet100-arcface.onnx",
        "mobilefacenet_onnx": PROJECT_ROOT / "models" / "mobilefacenet.onnx",
        "insightface_buffalo_l": None,
    }
    selected: list[str] = []
    for model in models:
        if model in {"mock", "arcface_onnx", "mobilefacenet_onnx", "insightface_buffalo_l"}:
            if model == "arcface_onnx" and not model_paths[model].exists():
                if skip_missing_models:
                    print(f"Skipping {model}: missing {model_paths[model]}")
                    continue
                raise SystemExit(f"Missing required model artifact for {model}: {model_paths[model]}")
            if model == "mobilefacenet_onnx" and not model_paths[model].exists():
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
    args = parser.parse_args()

    settings = get_settings()
    output_dir = Path(args.output or settings.benchmark_output_dir)
    ok, statuses = validate_model_artifacts(models_dir=PROJECT_ROOT / "models", root_dir=PROJECT_ROOT)
    required_missing = [item for item in statuses if item["required"] and item["status"] == "MISSING"]
    if required_missing and not args.skip_missing_models:
        missing_paths = ", ".join(item["name"] for item in required_missing)
        print(f"Missing required model artifact(s): {missing_paths}")
        raise SystemExit(1)
    if required_missing:
        print("Skipping benchmark for missing required model artifacts:")
        for item in required_missing:
            print(f"- {item['name']}: {item['path']}")

    models_to_run = _resolve_models_to_run(args.models, skip_missing_models=args.skip_missing_models)
    if not models_to_run:
        print("No runnable models remain after model validation")
        output_dir.mkdir(parents=True, exist_ok=True)
        generate_benchmark_report([], output_dir=output_dir, dataset_name="benchmark")
        print("Benchmark complete")
        return

    runner = BenchmarkRunner(models=models_to_run, dataset_path=args.dataset, threshold=args.threshold)
    results = runner.run()
    paths = generate_benchmark_report(results, output_dir=output_dir, dataset_name="benchmark")

    print("Benchmark complete")
    for path in paths.values():
        print(path)


if __name__ == "__main__":
    main()
