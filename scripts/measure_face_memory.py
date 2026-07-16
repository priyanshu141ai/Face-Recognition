"""Run a small, repeatable RSS probe for the active real face models."""

from __future__ import annotations

import base64
import ctypes
import gc
import io
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, TypeVar

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
T = TypeVar("T")
sys.path.insert(0, str(ROOT))


def _rss_mib() -> float:
    if sys.platform != "win32":
        statm = Path("/proc/self/statm")
        if not statm.exists():
            raise OSError("current RSS measurement is unsupported on this platform")
        resident_pages = int(statm.read_text(encoding="ascii").split()[1])
        return resident_pages * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024)

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("page_fault_count", ctypes.c_ulong),
            ("peak_working_set_size", ctypes.c_size_t),
            ("working_set_size", ctypes.c_size_t),
            ("quota_peak_paged_pool_usage", ctypes.c_size_t),
            ("quota_paged_pool_usage", ctypes.c_size_t),
            ("quota_peak_non_paged_pool_usage", ctypes.c_size_t),
            ("quota_non_paged_pool_usage", ctypes.c_size_t),
            ("pagefile_usage", ctypes.c_size_t),
            ("peak_pagefile_usage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    process = kernel32.GetCurrentProcess()
    if not psapi.GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
        raise OSError("GetProcessMemoryInfo failed")
    return counters.working_set_size / (1024 * 1024)


def _measure(operation: Callable[[], T]) -> tuple[T, float, float]:
    stop = threading.Event()
    peak = [_rss_mib()]

    def sample() -> None:
        while not stop.wait(0.002):
            peak[0] = max(peak[0], _rss_mib())

    sampler = threading.Thread(target=sample, daemon=True)
    started = time.perf_counter()
    sampler.start()
    try:
        result = operation()
    finally:
        stop.set()
        sampler.join()
    latency_ms = (time.perf_counter() - started) * 1000.0
    peak[0] = max(peak[0], _rss_mib())
    return result, peak[0], latency_ms


def _image_payload() -> dict[str, str]:
    axis = np.linspace(0, 255, 112, dtype=np.uint8)
    red = np.broadcast_to(axis, (112, 112))
    green = red.T
    blue = np.full((112, 112), 96, dtype=np.uint8)
    image = np.stack((red, green, blue), axis=-1)
    buffer = io.BytesIO()
    Image.fromarray(image, mode="RGB").save(buffer, format="PNG")
    return {
        "kind": "base64_png",
        "data": base64.b64encode(buffer.getvalue()).decode("ascii"),
    }


def main() -> None:
    before_initialization = _rss_mib()
    os.environ["DETECTOR_PROVIDER"] = "yunet"
    os.environ["RECOGNIZER_PROVIDER"] = "arcface_onnx"
    os.environ["YUNET_MODEL_PATH"] = str(ROOT / "models" / "face_detection_yunet_2023mar.onnx")
    os.environ["ARCFACE_MODEL_PATH"] = str(ROOT / "models" / "face-recognition-resnet100-arcface.onnx")

    from app.schemas.ess import FaceRegisterRequest
    from app.schemas.face import FaceDetectionSchema, VerifyRequest
    from app.services.face_enrollment import extract_fused_face_template
    from app.services.pipeline import get_face_verification_pipeline

    pipeline = get_face_verification_pipeline()
    pipeline.ensure_ready()
    after_models_ready = _rss_mib()
    real_detector = pipeline.detector

    detection = FaceDetectionSchema(
        bbox_xywh=[0.0, 0.0, 112.0, 112.0],
        landmarks5=[
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041],
        ],
        detection_confidence=0.99,
    )

    class DeterministicDetector:
        def detect(self, image: bytes, quality_policy=None):
            real_detector.detect(image, quality_policy)
            return [detection]

    pipeline.detector = DeterministicDetector()
    image = _image_payload()
    verify_request = VerifyRequest.model_validate(
        {"request_id": "rss-verify", "image_a": image, "image_b": image}
    )
    register_request = FaceRegisterRequest.model_validate(
        {
            "request_id": "rss-register",
            "enrollment_images": [
                {"angle": angle, "image": image}
                for angle in ("front", "left", "right")
            ],
        }
    )

    _, verification_peak, verification_latency = _measure(
        lambda: pipeline.verify(verify_request, pipeline.settings.max_image_mb)
    )
    rss_after_verification = _rss_mib()
    _, registration_peak, registration_latency = _measure(
        lambda: extract_fused_face_template(register_request, pipeline.settings.max_image_mb)
    )
    rss_after_registration = _rss_mib()

    sequential_latencies = []
    sequential_peak = _rss_mib()
    for index in range(5):
        request = verify_request.model_copy(update={"request_id": f"rss-sequential-{index}"})
        _, peak, latency = _measure(
            lambda current=request: pipeline.verify(current, pipeline.settings.max_image_mb)
        )
        sequential_peak = max(sequential_peak, peak)
        sequential_latencies.append(latency)
    rss_after_five_verifications = _rss_mib()

    def verify_concurrently(index: int) -> dict[str, object]:
        request = verify_request.model_copy(update={"request_id": f"rss-concurrent-{index}"})
        return pipeline.verify(request, pipeline.settings.max_image_mb)

    def run_concurrent() -> None:
        with ThreadPoolExecutor(max_workers=2) as executor:
            list(executor.map(verify_concurrently, range(2)))

    _, concurrent_peak, concurrent_latency = _measure(run_concurrent)
    gc.collect()
    time.sleep(0.1)
    idle_rss = _rss_mib()

    print(
        json.dumps(
            {
                "rss_mib": {
                    "before_initialization": round(before_initialization, 2),
                    "after_models_ready": round(after_models_ready, 2),
                    "after_one_verification": round(rss_after_verification, 2),
                    "after_one_registration": round(rss_after_registration, 2),
                    "after_five_verifications": round(rss_after_five_verifications, 2),
                    "idle": round(idle_rss, 2),
                    "verification_peak": round(verification_peak, 2),
                    "registration_peak": round(registration_peak, 2),
                    "five_verification_peak": round(sequential_peak, 2),
                    "two_concurrent_verification_peak": round(concurrent_peak, 2),
                },
                "latency_ms": {
                    "verification": round(verification_latency, 2),
                    "registration": round(registration_latency, 2),
                    "five_verification_mean": round(float(np.mean(sequential_latencies)), 2),
                    "two_concurrent_verifications_total": round(concurrent_latency, 2),
                },
                "model_identity": {
                    "pipeline": id(pipeline),
                    "yunet": id(real_detector),
                    "arcface": id(pipeline.recognizer),
                    "arcface_session": id(pipeline.recognizer.session),
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
