import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.validation.checks import check_benchmark_dataset, check_file_exists
from app.validation.report import ValidationReport


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="benchmark_data")
    args = parser.parse_args()

    report = ValidationReport()
    report.extend(check_benchmark_dataset(PROJECT_ROOT / args.dataset))
    report.add(check_file_exists(PROJECT_ROOT / "scripts/run_benchmark.py", "Benchmark"))
    report.add(check_file_exists(PROJECT_ROOT / "scripts/compare_models.py", "Benchmark"))
    report.print_table()
    raise SystemExit(0 if report.overall_status == "PASS" else 1)


if __name__ == "__main__":
    main()
