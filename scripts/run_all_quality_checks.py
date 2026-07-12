import argparse
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
    check_python_dependencies,
    check_required_project_structure,
)
from app.validation.report import ValidationReport, ValidationResult


def _api_running(base_url: str) -> bool:
    try:
        return httpx.get(f"{base_url.rstrip('/')}/healthz", timeout=2.0).status_code < 500
    except Exception:
        return False


def _run(name: str, args: list[str], warn_codes: set[int] | None = None) -> ValidationResult:
    result = subprocess.run([sys.executable, *args], cwd=PROJECT_ROOT, capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip().splitlines()
    detail = output[-1] if output else "ok"
    warn_codes = warn_codes or set()
    status = "PASS" if result.returncode == 0 else ("WARN" if result.returncode in warn_codes else "FAIL")
    return ValidationResult(name, "Command", status, detail)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["auto", "mock", "real"], default="auto")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dataset", default="benchmark_data/lfw")
    parser.add_argument("--skip-api", action="store_true")
    parser.add_argument("--skip-benchmark", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--json-output", default="qa_report.json")
    parser.add_argument("--md-output", default="qa_report.md")
    args = parser.parse_args()

    settings = get_settings()
    mode = args.mode
    if mode == "auto":
        mode = "real" if settings.detector_provider == "yunet" and settings.recognizer_provider == "arcface_onnx" else "mock"

    report = ValidationReport()
    report.extend(check_required_project_structure(PROJECT_ROOT))
    report.add(check_python_dependencies(PROJECT_ROOT))
    report.extend(check_env_config(settings))
    report.add(check_logging_safety_static(PROJECT_ROOT))
    report.extend(check_docker_readiness(PROJECT_ROOT))

    if mode == "real":
        report.add(_run("Real model artifacts", ["scripts/validate_model_artifacts.py"], warn_codes={2}))
    else:
        report.add(ValidationResult("Real model artifacts", "Models", "WARN", "skipped in mock mode"))

    if not args.skip_benchmark:
        report.extend(check_benchmark_dataset(PROJECT_ROOT / args.dataset))
        report.add(_run("Benchmark smoke", ["scripts/smoke_test_benchmark.py", "--dataset", args.dataset]))

    if not args.skip_pytest:
        report.add(_run("pytest", ["-m", "pytest", "-q"]))

    if args.skip_api:
        report.add(ValidationResult("API smoke", "API", "SKIP", "skipped"))
    elif _api_running(args.base_url):
        report.add(_run("Active model mode", ["scripts/check_active_model_mode.py", "--base-url", args.base_url, "--expected", mode]))
        report.add(_run("API smoke", ["scripts/smoke_test_api.py", "--base-url", args.base_url]))
        report.add(_run("Image edge cases", ["scripts/test_image_edge_cases.py", "--base-url", args.base_url], warn_codes={2}))
        report.add(_run("Performance sanity", ["scripts/performance_sanity_check.py", "--base-url", args.base_url], warn_codes={2}))
    else:
        report.add(ValidationResult("API smoke", "API", "WARN", "API not running"))

    report.print_table()
    report.save_json(PROJECT_ROOT / args.json_output)
    report.save_markdown(PROJECT_ROOT / args.md_output)

    failed = report.failed_checks()
    warned = [item for item in report.results if item.status == "WARN"]
    print()
    print(f"Overall: {'FAIL' if failed else ('PASS_WITH_WARNINGS' if warned else 'PASS')}")
    raise SystemExit(1 if failed else (2 if warned else 0))


if __name__ == "__main__":
    main()
