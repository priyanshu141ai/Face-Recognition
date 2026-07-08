import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.benchmark.model_artifacts import inspect_onnx_model

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


ARTIFACTS = [
    {
        "name": "YuNet detector",
        "file": "face_detection_yunet_2023mar.onnx",
        "required": True,
        "min_bytes": 100_000,
        "kind": "yunet",
    },
    {
        "name": "ArcFace ResNet100 ONNX",
        "file": "face-recognition-resnet100-arcface.onnx",
        "required": True,
        "min_bytes": 10_000_000,
        "kind": "arcface",
    },
    {
        "name": "MobileFaceNet ONNX",
        "file": "mobilefacenet.onnx",
        "required": False,
        "min_bytes": 1_000_000,
        "kind": "optional",
    },
]


def _shape_has_arcface_contract(meta: dict[str, object]) -> bool:
    inputs = meta.get("input_shapes") or []
    outputs = meta.get("output_shapes") or []
    flat_in = [str(item) for shape in inputs for item in shape]
    flat_out = [str(item) for shape in outputs for item in shape]
    return "3" in flat_in and "112" in flat_in and "512" in flat_out


def _extra_check(path: Path, kind: str, meta: dict[str, object]) -> tuple[str, str]:
    if kind == "yunet":
        if cv2 is None or not hasattr(cv2, "FaceDetectorYN"):
            return "WARN", "OpenCV FaceDetectorYN not available"
        try:
            cv2.FaceDetectorYN.create(str(path), "", (320, 320))
            return "PASS", "OpenCV YuNet init OK"
        except Exception as exc:
            return "FAIL", f"YuNet init failed: {exc}"
    if kind == "arcface":
        if meta.get("status") != "LOADED":
            return "FAIL", str(meta.get("error", "ONNX load failed"))
        if not _shape_has_arcface_contract(meta):
            return "FAIL", f"unexpected input/output shapes: {meta.get('input_shapes')} -> {meta.get('output_shapes')}"
        return "PASS", f"input={meta.get('input_names')} output={meta.get('output_names')}"
    return ("PASS", "optional ONNX load OK") if meta.get("status") == "LOADED" else ("WARN", str(meta.get("error", "optional model not loaded")))


def validate(models_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in ARTIFACTS:
        path = models_dir / item["file"]
        required = bool(item["required"])
        if not path.exists():
            rows.append({"model": item["name"], "required": str(required), "status": "FAIL" if required else "WARN", "details": "missing", "path": str(path)})
            continue
        size = path.stat().st_size
        if size < int(item["min_bytes"]):
            rows.append({"model": item["name"], "required": str(required), "status": "FAIL" if required else "WARN", "details": f"too small: {size} bytes", "path": str(path)})
            continue
        meta = inspect_onnx_model(path)
        status = "PASS" if meta.get("status") == "LOADED" else ("FAIL" if required else "WARN")
        details = f"size={size} bytes; onnx={meta.get('status')}"
        extra_status, extra_details = _extra_check(path, str(item["kind"]), meta)
        if extra_status == "FAIL":
            status = "FAIL"
        elif extra_status == "WARN" and status == "PASS":
            status = "WARN"
        rows.append({"model": item["name"], "required": str(required), "status": status, "details": f"{details}; {extra_details}", "path": str(path)})
    return rows


def _table(rows: list[dict[str, str]]) -> str:
    headers = ["Model", "Required", "Status", "Details", "Path"]
    body = [[r["model"], r["required"], r["status"], r["details"], r["path"]] for r in rows]
    widths = [len(h) for h in headers]
    for row in body:
        widths = [max(widths[i], len(row[i])) for i in range(len(headers))]

    def fmt(row: list[str]) -> str:
        return "  ".join(row[i].ljust(widths[i]) for i in range(len(headers)))

    return "\n".join([fmt(headers), fmt(["-" * w for w in widths]), *[fmt(row) for row in body]])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models-dir", default="models")
    args = parser.parse_args()

    models_dir = (PROJECT_ROOT / args.models_dir).resolve()
    rows = validate(models_dir)
    print(_table(rows))
    required_fail = [row for row in rows if row["required"] == "True" and row["status"] == "FAIL"]
    warnings = [row for row in rows if row["status"] == "WARN"]
    if required_fail:
        raise SystemExit(1)
    if warnings:
        print("Required models OK. Optional warnings exist.")
        raise SystemExit(2)
    print("All required and optional model artifacts OK.")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
