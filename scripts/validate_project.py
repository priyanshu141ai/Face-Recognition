import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.validation.checks import check_docker_readiness, check_python_dependencies, check_required_project_structure
from app.validation.report import ValidationReport


def main() -> None:
    report = ValidationReport()
    report.extend(check_required_project_structure(PROJECT_ROOT))
    report.add(check_python_dependencies(PROJECT_ROOT))
    report.extend(check_docker_readiness(PROJECT_ROOT))
    report.print_table()
    raise SystemExit(0 if report.overall_status == "PASS" else 1)


if __name__ == "__main__":
    main()
