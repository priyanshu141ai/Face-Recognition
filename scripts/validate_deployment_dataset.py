import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.validation.deployment import validate_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--skip-file-checks", action="store_true")
    parser.add_argument("--approved-demographic-field", action="append", default=[])
    parser.add_argument("--governance-approval-reference")
    args = parser.parse_args()
    result = validate_manifest(
        args.manifest,
        check_files=not args.skip_file_checks,
        approved_demographic_fields=set(args.approved_demographic_field),
        governance_approval_reference=args.governance_approval_reference,
    )
    print(json.dumps({
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "pairs": len(result.rows),
        "genuine_pairs": result.genuine_pairs,
        "impostor_pairs": result.impostor_pairs,
    }, indent=2))
    raise SystemExit(0 if result.valid else 1)


if __name__ == "__main__":
    main()
