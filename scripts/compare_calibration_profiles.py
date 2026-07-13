import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


FIELDS = ("schema_version", "calibration_version", "model_provider", "model_sha256", "dataset_version", "target_fmr", "threshold", "approval_status")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile_a")
    parser.add_argument("profile_b")
    args = parser.parse_args()
    profiles = [json.loads(Path(path).read_text(encoding="utf-8")) for path in (args.profile_a, args.profile_b)]
    print(json.dumps({field: [profiles[0].get(field), profiles[1].get(field)] for field in FIELDS}, indent=2))


if __name__ == "__main__":
    main()
