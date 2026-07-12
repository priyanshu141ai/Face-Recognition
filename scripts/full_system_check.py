import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.validation.checks import (
    check_benchmark_dataset,
    check_docker_readiness,
    check_env_config,
    check_logging_safety_static,
    check_model_artifacts,
    check_python_dependencies,
    check_required_project_structure,
)
from app.validation.report import ValidationReport, ValidationResult


def _api_running(base_url: str) -> bool:
    try:
        return httpx.get(f"{base_url.rstrip('/')}/healthz", timeout=2.0).status_code < 500
    except Exception:
        return False


def _run_script(args: list[str]) -> ValidationResult:
    result = subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, capture_output=True, text=True)
    name = Path(args[0]).name
    details = "ok" if result.returncode == 0 else (result.stdout + result.stderr).strip().splitlines()[-1:]
    if isinstance(details, list):
        details = details[0] if details else "failed"
    return ValidationResult(name, "Subprocess", "PASS" if result.returncode == 0 else "FAIL", details)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dataset", default="benchmark_data/lfw")
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--skip-models", action="store_true")
    parser.add_argument("--skip-benchmark", action="store_true")
    parser.add_argument("--json-output")
    parser.add_argument("--md-output")
    parser.add_argument("--docker-build-check", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    report = ValidationReport()
    report.extend(check_required_project_structure(PROJECT_ROOT))
    report.add(check_python_dependencies(PROJECT_ROOT))
    report.extend(check_env_config(settings))

    if args.skip_models:
        report.add(ValidationResult("Model artifacts", "Models", "SKIP", "skipped"))
    else:
        report.extend(check_model_artifacts(settings, PROJECT_ROOT))
        report.add(_run_script(["scripts/smoke_test_models.py"]))

    if args.skip_benchmark:
        report.add(ValidationResult("Benchmark readiness", "Benchmark", "SKIP", "skipped"))
    else:
        report.extend(check_benchmark_dataset(PROJECT_ROOT / args.dataset))
        report.add(_run_script(["scripts/smoke_test_benchmark.py", "--dataset", args.dataset]))

    if args.skip_api:
        report.add(ValidationResult("API endpoints", "API", "SKIP", "skipped"))
    elif _api_running(args.base_url):
        report.add(_run_script(["scripts/smoke_test_api.py", "--base-url", args.base_url]))
    else:
        report.add(ValidationResult("API endpoints", "API", "WARN", "API is not running"))

    report.add(check_logging_safety_static(PROJECT_ROOT))
    report.extend(check_docker_readiness(PROJECT_ROOT))
    if args.docker_build_check:
        if shutil.which("docker") is None:
            report.add(ValidationResult("Docker build", "Docker", "WARN", "docker not installed"))
        else:
            result = subprocess.run(["docker", "build", "-t", "face-recognition-backend:test", "."], cwd=PROJECT_ROOT)
            report.add(ValidationResult("Docker build", "Docker", "PASS" if result.returncode == 0 else "FAIL", "docker build"))

    print("Full System Validation Summary")
    print()
    report.print_table()
    print()
    print(f"Overall Status: {report.overall_status}")
    if report.failed_checks():
        print("Failed checks:")
        for item in report.failed_checks():
            print(f"- {item.check_name}: {item.details}")

    if args.json_output:
        report.save_json(args.json_output)
    if args.md_output:
        report.save_markdown(args.md_output)
    raise SystemExit(0 if report.overall_status == "PASS" else 1)


if __name__ == "__main__":
    main()
