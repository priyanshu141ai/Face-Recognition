import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.benchmark.model_artifacts import generate_sample_pairs_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", default="benchmark_data/images")
    parser.add_argument("--output", default="benchmark_data/pairs.csv")
    args = parser.parse_args()

    output_path = generate_sample_pairs_csv(images_dir=args.images, output_path=args.output)
    print(f"Created sample pairs template at {output_path}")
    print("Please review labels manually before running benchmarks.")


if __name__ == "__main__":
    main()
