import base64
import hashlib
import io
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings, validate_deployment_settings
from app.main import app
from app.models import arcface_onnx_recognizer as arcface_module
from app.models.arcface_onnx_recognizer import ArcFaceOnnxRecognizer
from app.models.yunet_detector import YuNetFaceDetector
from app.services import pipeline as pipeline_module
from app.services.pipeline import FaceVerificationPipeline, _pipeline_for_settings


def _image() -> dict[str, str]:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (20, 40, 60)).save(buffer, format="PNG")
    return {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}


def _verify_payload(request_id: str) -> dict[str, object]:
    image = _image()
    return {"request_id": request_id, "image_a": image, "image_b": image}


def test_real_model_objects_initialize_once_under_concurrent_readiness(monkeypatch) -> None:
    counts = {"yunet": 0, "arcface": 0}

    class Detector:
        def __init__(self, _settings):
            counts["yunet"] += 1

    class Recognizer:
        def __init__(self, _settings):
            counts["arcface"] += 1

    monkeypatch.setattr(pipeline_module, "YuNetFaceDetector", Detector)
    monkeypatch.setattr(pipeline_module, "ArcFaceOnnxRecognizer", Recognizer)
    pipeline = FaceVerificationPipeline(
        Settings(detector_provider="yunet", recognizer_provider="arcface_onnx")
    )
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(lambda _: pipeline.ensure_ready(), range(8)))
    assert counts == {"yunet": 1, "arcface": 1}


def test_arcface_inference_session_is_created_once_with_thread_limits(monkeypatch, tmp_path) -> None:
    model = tmp_path / "arcface.onnx"
    model.write_bytes(b"arcface-test-model")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    created = []

    class SessionOptions:
        intra_op_num_threads = None
        inter_op_num_threads = None

    class Session:
        def __init__(self, _path, *, sess_options, providers):
            created.append((sess_options, providers))

        def get_inputs(self):
            return [SimpleNamespace(name="input")]

        def get_outputs(self):
            return [SimpleNamespace(name="output")]

        def run(self, _outputs, _inputs):
            return [np.ones((1, 512), dtype=np.float32)]

    monkeypatch.setattr(
        arcface_module,
        "ort",
        SimpleNamespace(SessionOptions=SessionOptions, InferenceSession=Session),
    )
    settings = Settings(
        arcface_model_path=str(model),
        arcface_sha256=digest,
        ort_intra_op_threads=3,
        ort_inter_op_threads=1,
    )
    recognizer = ArcFaceOnnxRecognizer(settings)
    recognizer.embed(np.zeros((112, 112, 3), dtype=np.uint8))
    recognizer.embed(np.ones((112, 112, 3), dtype=np.uint8))
    assert len(created) == 1
    assert created[0][0].intra_op_num_threads == 3
    assert created[0][0].inter_op_num_threads == 1


def test_shared_yunet_detector_serializes_mutable_detector_execution() -> None:
    active = 0
    maximum = 0
    state_lock = threading.Lock()

    class Detector:
        def setInputSize(self, _size):
            pass

        def detect(self, _image):
            nonlocal active, maximum
            with state_lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.03)
            with state_lock:
                active -= 1
            return None

    detector = YuNetFaceDetector.__new__(YuNetFaceDetector)
    detector.settings = Settings()
    detector.detector = Detector()
    detector._detector_lock = threading.Lock()
    image_bytes = base64.b64decode(_image()["data"])
    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(detector.detect, (image_bytes, image_bytes)))
    assert maximum == 1


def test_multiple_api_requests_reuse_models_and_keep_request_data_local(monkeypatch) -> None:
    pipeline = FaceVerificationPipeline(Settings())
    pipeline.ensure_ready()
    detector_id = id(pipeline.detector)
    recognizer_id = id(pipeline.recognizer)
    monkeypatch.setattr(
        "app.api.v1.routes_faces.get_face_verification_pipeline", lambda: pipeline
    )
    client = TestClient(app)
    first = client.post("/v1/faces/verify", json=_verify_payload("request-one"))
    second = client.post("/v1/faces/verify", json=_verify_payload("request-two"))
    assert first.status_code == second.status_code == 200
    assert first.json()["request_id"] == "request-one"
    assert second.json()["request_id"] == "request-two"
    assert id(pipeline.detector) == detector_id
    assert id(pipeline.recognizer) == recognizer_id
    assert first.json()["timings_ms"] is not second.json()["timings_ms"]


def test_inference_semaphore_bounds_work_and_releases_waiters(monkeypatch) -> None:
    pipeline = FaceVerificationPipeline(Settings(face_inference_concurrency=2))
    release = threading.Event()
    two_active = threading.Event()
    state_lock = threading.Lock()
    active = 0
    maximum = 0

    def work(request, _max_image_mb):
        nonlocal active, maximum
        with state_lock:
            active += 1
            maximum = max(maximum, active)
            if active == 2:
                two_active.set()
        assert release.wait(2)
        with state_lock:
            active -= 1
        return request.request_id

    monkeypatch.setattr(pipeline, "_verify_unlocked", work)
    requests = [SimpleNamespace(request_id=f"request-{index}") for index in range(4)]
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(pipeline.verify, request, 5.0) for request in requests]
        assert two_active.wait(1)
        assert sum(future.done() for future in futures) == 0
        release.set()
        assert [future.result(timeout=2) for future in futures] == [
            request.request_id for request in requests
        ]
    assert maximum == 2


def test_blocking_inference_does_not_block_lightweight_fastapi_endpoint() -> None:
    pipeline = FaceVerificationPipeline(Settings(face_inference_concurrency=1))
    entered = threading.Event()
    release = threading.Event()
    test_app = FastAPI()

    @test_app.get("/model")
    def model_endpoint():
        with pipeline.inference_slot():
            entered.set()
            assert release.wait(2)
        return {"status": "done"}

    @test_app.get("/light")
    def light_endpoint():
        return {"status": "ok"}

    with TestClient(test_app) as client, ThreadPoolExecutor(max_workers=1) as executor:
        model_future = executor.submit(client.get, "/model")
        assert entered.wait(1)
        started = time.perf_counter()
        light = client.get("/light")
        elapsed = time.perf_counter() - started
        release.set()
        assert model_future.result(timeout=2).status_code == 200
    assert light.status_code == 200
    assert elapsed < 0.5


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("FACE_INFERENCE_CONCURRENCY", "0"),
        ("FACE_INFERENCE_CONCURRENCY", "not-an-int"),
        ("ORT_INTRA_OP_THREADS", "0"),
        ("ORT_INTER_OP_THREADS", "0"),
    ],
)
def test_invalid_model_concurrency_configuration_is_rejected(monkeypatch, name, value) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=name):
        Settings.from_env()


def test_direct_settings_validation_rejects_invalid_inference_concurrency() -> None:
    assert Settings().app_replica_count == 1
    assert Settings().face_inference_concurrency == 2
    assert Settings().ort_intra_op_threads == 2
    assert Settings().ort_inter_op_threads == 1
    with pytest.raises(RuntimeError, match="FACE_INFERENCE_CONCURRENCY"):
        validate_deployment_settings(Settings(face_inference_concurrency=0))


def test_application_startup_fails_when_required_models_cannot_load(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DETECTOR_PROVIDER", "yunet")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "arcface_onnx")
    monkeypatch.setenv("YUNET_MODEL_PATH", str(tmp_path / "missing-yunet.onnx"))
    monkeypatch.setenv("ARCFACE_MODEL_PATH", str(tmp_path / "missing-arcface.onnx"))
    _pipeline_for_settings.cache_clear()
    try:
        with pytest.raises(FileNotFoundError, match="YuNet model not found"):
            with TestClient(app):
                pass
    finally:
        _pipeline_for_settings.cache_clear()


def test_production_startup_uses_one_worker_without_reload() -> None:
    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    powershell = (root / "scripts" / "start_real_mode.ps1").read_text(encoding="utf-8")
    shell = (root / "scripts" / "start_real_mode.sh").read_text(encoding="utf-8")
    for command in (dockerfile, powershell, shell):
        assert "--workers" in command and "1" in command
        assert "--reload" not in command
