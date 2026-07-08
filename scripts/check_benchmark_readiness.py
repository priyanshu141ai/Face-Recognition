import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.benchmark.model_artifacts import evaluate_benchmark_readiness


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="benchmark_data")
    args = parser.parse_args()

    readiness = evaluate_benchmark_readiness(args.dataset)
    print("Benchmark readiness report")
    print("-" * 28)
    print(f"Dataset: {args.dataset}")
    print(f"Status: {'READY' if readiness['ok'] else 'NOT READY'}")
    print(f"Genuine pairs: {readiness['genuine_pairs']}")
    print(f"Impostor pairs: {readiness['impostor_pairs']}")
    if readiness["errors"]:
        print("Errors:")
        for error in readiness["errors"]:
            print(f"- {error}")
    else:
        print("No errors found.")

    raise SystemExit(0 if readiness["ok"] else 1)


if __name__ == "__main__":
    main()
