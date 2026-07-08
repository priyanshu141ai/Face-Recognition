from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path


VALID_STATUSES = {"PASS", "FAIL", "WARN", "SKIP"}


@dataclass
class ValidationResult:
    check_name: str
    category: str
    status: str
    details: str = ""
    duration_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"invalid validation status: {self.status}")


@dataclass
class ValidationReport:
    results: list[ValidationResult] = field(default_factory=list)

    def add(self, result: ValidationResult) -> None:
        self.results.append(result)

    def extend(self, results: list[ValidationResult]) -> None:
        self.results.extend(results)

    @property
    def overall_status(self) -> str:
        return "FAIL" if any(item.status == "FAIL" for item in self.results) else "PASS"

    def failed_checks(self) -> list[ValidationResult]:
        return [item for item in self.results if item.status == "FAIL"]

    def print_table(self) -> None:
        print(self.to_table())

    def to_table(self) -> str:
        headers = ["Check Name", "Category", "Status", "Details", "ms"]
        rows = [
            [r.check_name, r.category, r.status, r.details, f"{r.duration_ms:.1f}"]
            for r in self.results
        ]
        widths = [len(h) for h in headers]
        for row in rows:
            widths = [max(widths[i], len(str(cell))) for i, cell in enumerate(row)]

        def fmt(row: list[str]) -> str:
            return "  ".join(str(cell).ljust(widths[i]) for i, cell in enumerate(row))

        return "\n".join([fmt(headers), fmt(["-" * w for w in widths]), *[fmt(row) for row in rows]])

    def to_json(self) -> dict[str, object]:
        return {
            "overall_status": self.overall_status,
            "results": [asdict(item) for item in self.results],
        }

    def to_markdown(self) -> str:
        lines = [
            "# Validation Report",
            "",
            f"Overall Status: {self.overall_status}",
            "",
            "| Check | Category | Status | Details | ms |",
            "| --- | --- | --- | --- | --- |",
        ]
        for r in self.results:
            lines.append(
                f"| {r.check_name} | {r.category} | {r.status} | {r.details} | {r.duration_ms:.1f} |"
            )
        return "\n".join(lines)

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_json(), indent=2), encoding="utf-8")

    def save_markdown(self, path: str | Path) -> None:
        Path(path).write_text(self.to_markdown(), encoding="utf-8")


def timed_result(check_name: str, category: str, fn) -> ValidationResult:
    start = time.perf_counter()
    try:
        status, details = fn()
    except Exception as exc:
        status, details = "FAIL", str(exc)
    return ValidationResult(
        check_name=check_name,
        category=category,
        status=status,
        details=details,
        duration_ms=round((time.perf_counter() - start) * 1000.0, 2),
    )
