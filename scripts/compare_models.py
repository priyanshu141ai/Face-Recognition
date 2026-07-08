import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports", required=True)
    args = parser.parse_args()

    reports_dir = Path(args.reports)
    summary_files = sorted(reports_dir.glob("summary_*.json"))
    frames = []
    for path in summary_files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for model in data.get("models", []):
            frames.append({"report": path.name, **model})
    if not frames:
        print("No benchmark summaries found")
        return
    df = pd.DataFrame(frames)
    print(df[["report", "model_name", "auc", "eer", "fnmr_at_fmr_1e-3", "avg_latency_ms", "failures"]].to_string(index=False))


if __name__ == "__main__":
    main()
