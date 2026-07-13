import argparse
import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.validation.deployment import REQUIRED_COLUMNS


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an empty privacy-aware deployment validation manifest.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        csv.DictWriter(handle, fieldnames=sorted(REQUIRED_COLUMNS)).writeheader()
    print(target)


if __name__ == "__main__":
    main()
