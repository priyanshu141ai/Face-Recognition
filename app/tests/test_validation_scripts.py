import subprocess
import sys
from pathlib import Path

from app.validation.checks import check_file_exists
from app.validation.report import ValidationReport, ValidationResult


def test_validation_report_object_works(tmp_path: Path) -> None:
    report = ValidationReport()
    report.add(ValidationResult("demo", "Unit", "PASS", "ok"))
    assert report.overall_status == "PASS"
    assert "demo" in report.to_table()
    json_path = tmp_path / "report.json"
    md_path = tmp_path / "report.md"
    report.save_json(json_path)
    report.save_markdown(md_path)
    assert json_path.exists()
    assert md_path.exists()


def test_missing_file_reports_fail(tmp_path: Path) -> None:
    result = check_file_exists(tmp_path / "missing.txt")
    assert result.status == "FAIL"


def test_validate_project_script_runs() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "scripts/validate_project.py"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
