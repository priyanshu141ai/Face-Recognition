"""Run an identical production-style local Docker RAM comparison."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any


CPU_LIMIT = "2"
MEMORY_LIMIT = "2g"
CONTAINER_PORT = 8080
HOST_PORT = 18080
SAMPLE_INTERVAL_SECONDS = 0.02


def _docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _image_payload(path: Path) -> dict[str, str]:
    suffix = path.suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png"}:
        raise ValueError("test image must be JPEG or PNG")
    kind = "base64_png" if suffix == ".png" else "base64_jpeg"
    return {"kind": kind, "data": base64.b64encode(path.read_bytes()).decode("ascii")}


def _request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 120.0,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    started = time.perf_counter()
    try:
        response = urllib.request.urlopen(request, timeout=timeout)
        status = response.status
        raw = response.read()
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read()
    latency_ms = (time.perf_counter() - started) * 1000.0
    try:
        body = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        body = {"unparseable_response": True}
    return {"status": status, "body": body, "latency_ms": latency_ms}


def _require_status(response: dict[str, Any], expected: int, label: str) -> None:
    if response["status"] != expected:
        body = response.get("body")
        raise RuntimeError(f"{label} returned HTTP {response['status']}: {body}")


def _memory_to_mib(value: str) -> float:
    match = re.fullmatch(r"([0-9.]+)([KMG]?i?B)", value.strip())
    if not match:
        raise ValueError(f"unsupported Docker memory value: {value}")
    amount = float(match.group(1))
    unit = match.group(2)
    factors = {
        "B": 1 / (1024 * 1024),
        "KB": 1000 / (1024 * 1024),
        "KiB": 1 / 1024,
        "MB": 1_000_000 / (1024 * 1024),
        "MiB": 1,
        "GB": 1_000_000_000 / (1024 * 1024),
        "GiB": 1024,
    }
    return amount * factors[unit]


def _docker_stats(container: str) -> dict[str, float]:
    raw = _docker("stats", "--no-stream", "--format", "{{json .}}", container).stdout.strip()
    stats = json.loads(raw)
    current = stats["MemUsage"].split("/")[0].strip()
    return {
        "memory_mib": _memory_to_mib(current),
        "cpu_percent": float(stats["CPUPerc"].rstrip("%")),
    }


class CgroupSampler:
    """Sample Docker-style cgroup working set and CPU counters."""

    def __init__(self, container: str) -> None:
        self.container = container
        self.samples: list[tuple[int, int, int]] = []
        self._lock = threading.Lock()
        self._reader: threading.Thread | None = None
        self._process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        _docker("exec", self.container, "sh", "-c", "rm -f /tmp/docker_ram_sampler_stop")
        code = (
            "import pathlib,time\n"
            "stop=pathlib.Path('/tmp/docker_ram_sampler_stop')\n"
            "while not stop.exists():\n"
            " current=int(pathlib.Path('/sys/fs/cgroup/memory.current').read_text())\n"
            " memstat={line.split()[0]:int(line.split()[1]) for line in "
            "pathlib.Path('/sys/fs/cgroup/memory.stat').read_text().splitlines()}\n"
            " m=max(0,current-memstat.get('inactive_file',0))\n"
            " cpu={line.split()[0]:int(line.split()[1]) for line in "
            "pathlib.Path('/sys/fs/cgroup/cpu.stat').read_text().splitlines()}['usage_usec']\n"
            " print(f'{time.time_ns()}|{m}|{cpu}',flush=True)\n"
            f" time.sleep({SAMPLE_INTERVAL_SECONDS})\n"
        )
        self._process = subprocess.Popen(
            ["docker", "exec", self.container, "python", "-u", "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        def read_samples() -> None:
            assert self._process is not None and self._process.stdout is not None
            for line in self._process.stdout:
                parts = line.strip().split("|")
                if len(parts) == 3:
                    with self._lock:
                        self.samples.append(tuple(int(part) for part in parts))

        self._reader = threading.Thread(target=read_samples, daemon=True)
        self._reader.start()

    def stop(self) -> None:
        if self._process is None:
            return
        _docker("exec", self.container, "sh", "-c", "touch /tmp/docker_ram_sampler_stop", check=False)
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            self._process.wait(timeout=5)
        if self._reader is not None:
            self._reader.join(timeout=5)

    def _interval(self, started_ns: int, ended_ns: int) -> list[tuple[int, int, int]]:
        with self._lock:
            selected = [sample for sample in self.samples if started_ns <= sample[0] <= ended_ns]
            if selected:
                return selected
            nearby = sorted(self.samples, key=lambda sample: abs(sample[0] - ended_ns))
            return nearby[:1]

    def peak_mib(self, started_ns: int, ended_ns: int) -> float:
        selected = self._interval(started_ns, ended_ns)
        if not selected:
            raise RuntimeError("no cgroup memory samples were captured")
        return max(sample[1] for sample in selected) / (1024 * 1024)

    def cpu_peak_percent(self, started_ns: int | None = None, ended_ns: int | None = None) -> float:
        with self._lock:
            samples = list(self.samples)
        if started_ns is not None and ended_ns is not None:
            samples = [sample for sample in samples if started_ns <= sample[0] <= ended_ns]
        peaks = []
        for previous, current in zip(samples, samples[1:]):
            wall_usec = (current[0] - previous[0]) / 1000.0
            if wall_usec > 0:
                peaks.append((current[2] - previous[2]) / wall_usec * 100.0)
        return max(peaks, default=0.0)

    def maximum_mib(self) -> float:
        with self._lock:
            if not self.samples:
                raise RuntimeError("no cgroup samples were captured")
            return max(sample[1] for sample in self.samples) / (1024 * 1024)


def _wait_for_readiness(base_url: str, timeout_seconds: float = 180.0) -> tuple[dict[str, Any], dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            health = _request("GET", f"{base_url}/healthz", timeout=5)
            ready = _request("GET", f"{base_url}/readyz", timeout=120)
            if health["status"] == 200 and ready["status"] == 200:
                return health, ready
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(0.25)
    raise RuntimeError(f"container did not become ready: {last_error}")


def _wait_for_docker_health(container: str, timeout_seconds: float = 60.0) -> str:
    deadline = time.monotonic() + timeout_seconds
    status = "unknown"
    while time.monotonic() < deadline:
        status = _docker(
            "inspect", "--format", "{{.State.Health.Status}}", container
        ).stdout.strip()
        if status == "healthy":
            return status
        if status == "unhealthy":
            raise RuntimeError("Docker health check reported unhealthy")
        time.sleep(0.5)
    raise RuntimeError(f"Docker health status did not become healthy: {status}")


def _measure_call(call) -> tuple[Any, float, int, int]:
    started_ns = time.time_ns()
    started = time.perf_counter()
    value = call()
    latency_ms = (time.perf_counter() - started) * 1000.0
    time.sleep(0.1)
    ended_ns = time.time_ns()
    return value, latency_ms, started_ns, ended_ns


def _image_metadata(image: str) -> dict[str, Any]:
    inspected = json.loads(_docker("image", "inspect", image).stdout)[0]
    return {"id": inspected["Id"], "size_bytes": inspected["Size"]}


def _run_case(
    *,
    label: str,
    image: str,
    commit: str,
    models_dir: Path,
    data_dir: Path,
    image_payload: dict[str, str],
    environment: dict[str, str],
) -> dict[str, Any]:
    container = f"face-ram-{label}"
    if _docker("inspect", container, check=False).returncode == 0:
        raise RuntimeError(f"comparison container already exists: {container}")
    data_dir.mkdir(parents=True)
    base_url = f"http://127.0.0.1:{HOST_PORT}"
    command = [
        "run", "--detach", "--name", container,
        "--cpus", CPU_LIMIT, "--memory", MEMORY_LIMIT,
        "--publish", f"127.0.0.1:{HOST_PORT}:{CONTAINER_PORT}",
        "--mount", f"type=bind,source={models_dir},target=/app/models,readonly",
        "--mount", f"type=bind,source={data_dir},target=/app/data",
    ]
    for name, value in sorted(environment.items()):
        command.extend(("--env", f"{name}={value}"))
    command.append(image)

    sampler: CgroupSampler | None = None
    started_container = False
    startup_started = time.perf_counter()
    try:
        container_id = _docker(*command).stdout.strip()
        started_container = True
        sampler = CgroupSampler(container)
        sampler.start()
        health, ready = _wait_for_readiness(base_url)
        startup_to_ready_ms = (time.perf_counter() - startup_started) * 1000.0
        ready_stats = _docker_stats(container)

        auth_headers = {"Authorization": f"Bearer {environment['API_BEARER_TOKEN']}"}
        identity_headers = {
            **auth_headers,
            "X-User-ID": "ram-comparison-user",
            "X-Device-ID": "ram-device-0001",
        }
        model = _request("GET", f"{base_url}/v1/models/current", headers=auth_headers)
        _require_status(model, 200, "model metadata")
        device = _request(
            "POST",
            f"{base_url}/api/ess/device/register",
            headers=identity_headers,
            payload={"device_id": "ram-device-0001", "platform": "android"},
        )
        _require_status(device, 201, "device setup")

        idle_wait_started = time.monotonic()
        docker_health = _wait_for_docker_health(container)
        remaining = 30.0 - (time.monotonic() - idle_wait_started)
        if remaining > 0:
            time.sleep(remaining)
        idle_stats = _docker_stats(container)

        verify_payload = {
            "request_id": "docker-ram-verify-one",
            "image_a": image_payload,
            "image_b": image_payload,
        }
        verification, verification_latency, verify_start, verify_end = _measure_call(
            lambda: _request(
                "POST", f"{base_url}/v1/faces/verify",
                headers=auth_headers, payload=verify_payload,
            )
        )
        _require_status(verification, 200, "single verification")

        time.sleep(10)
        registration_payload = {
            "request_id": "docker-ram-registration",
            "enrollment_images": [
                {"angle": angle, "image": image_payload}
                for angle in ("front", "left", "right")
            ],
        }
        registration, registration_latency, register_start, register_end = _measure_call(
            lambda: _request(
                "POST", f"{base_url}/api/ess/face/register",
                headers=identity_headers, payload=registration_payload,
            )
        )
        _require_status(registration, 201, "three-angle registration")

        time.sleep(10)
        sequential_responses = []
        sequential_started_ns = time.time_ns()
        sequential_started = time.perf_counter()
        for index in range(5):
            payload = {**verify_payload, "request_id": f"docker-ram-sequential-{index}"}
            response = _request(
                "POST", f"{base_url}/v1/faces/verify",
                headers=auth_headers, payload=payload,
            )
            _require_status(response, 200, f"sequential verification {index}")
            sequential_responses.append(response)
        sequential_total_ms = (time.perf_counter() - sequential_started) * 1000.0
        time.sleep(0.1)
        sequential_ended_ns = time.time_ns()

        time.sleep(10)
        concurrent_started_ns = time.time_ns()
        concurrent_started = time.perf_counter()

        def concurrent_verify(index: int) -> dict[str, Any]:
            payload = {**verify_payload, "request_id": f"docker-ram-concurrent-{index}"}
            return _request(
                "POST", f"{base_url}/v1/faces/verify",
                headers=auth_headers, payload=payload,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            concurrent_responses = list(executor.map(concurrent_verify, range(2)))
        concurrent_total_ms = (time.perf_counter() - concurrent_started) * 1000.0
        for index, response in enumerate(concurrent_responses):
            _require_status(response, 200, f"concurrent verification {index}")
        time.sleep(0.1)
        concurrent_ended_ns = time.time_ns()

        time.sleep(30)
        final_stats = _docker_stats(container)
        logs = _docker("logs", container).stdout
        lowered_logs = logs.lower()
        model_errors = [
            marker for marker in (
                "model not found", "checksum does not match", "failed to load",
                "dependency_initialization_failed", "arcface inference failed",
            ) if marker in lowered_logs
        ]
        raw_payload_logged = image_payload["data"][:80] in logs
        embedding_array_logged = '"embeddings":' in lowered_logs
        if model_errors or raw_payload_logged or embedding_array_logged:
            raise RuntimeError("container logs failed model/payload safety validation")

        user = _docker("inspect", "--format", "{{.Config.User}}", container).stdout.strip()
        uid = _docker("exec", container, "id", "-u").stdout.strip()
        if user != "app" or uid == "0":
            raise RuntimeError(f"unexpected container user: config={user}, uid={uid}")

        assert sampler is not None
        result = {
            "label": label,
            "commit": commit,
            "image": _image_metadata(image),
            "container": {
                "id": container_id,
                "cpu_limit": float(CPU_LIMIT),
                "memory_limit_mib": 2048,
                "configured_user": user,
                "uid": int(uid),
            },
            "health": {
                "healthz_status": health["status"],
                "readyz_status": ready["status"],
                "docker_health": docker_health,
                "detector": model["body"].get("detector"),
                "recognizer": model["body"].get("recognizer"),
                "model_errors": model_errors,
            },
            "memory_mib": {
                "ready_current": ready_stats["memory_mib"],
                "idle_30s_current": idle_stats["memory_mib"],
                "verification_peak": sampler.peak_mib(verify_start, verify_end),
                "registration_peak": sampler.peak_mib(register_start, register_end),
                "five_sequential_peak": sampler.peak_mib(sequential_started_ns, sequential_ended_ns),
                "two_concurrent_peak": sampler.peak_mib(concurrent_started_ns, concurrent_ended_ns),
                "final_idle_30s_current": final_stats["memory_mib"],
                "maximum_observed": sampler.maximum_mib(),
            },
            "cpu_percent": {
                "docker_ready": ready_stats["cpu_percent"],
                "docker_idle": idle_stats["cpu_percent"],
                "docker_final": final_stats["cpu_percent"],
                "maximum_observed": sampler.cpu_peak_percent(),
            },
            "latency_ms": {
                "startup_to_ready": startup_to_ready_ms,
                "verification": verification_latency,
                "registration": registration_latency,
                "five_sequential_total": sequential_total_ms,
                "five_sequential_each": [item["latency_ms"] for item in sequential_responses],
                "two_concurrent_total": concurrent_total_ms,
                "two_concurrent_each": [item["latency_ms"] for item in concurrent_responses],
            },
            "behavior": {
                "verification_status": verification["status"],
                "verification_decision": verification["body"].get("decision"),
                "registration_status": registration["status"],
                "registration_result": registration["body"].get("status"),
                "sequential_statuses": [item["status"] for item in sequential_responses],
                "sequential_decisions": [item["body"].get("decision") for item in sequential_responses],
                "concurrent_statuses": [item["status"] for item in concurrent_responses],
                "concurrent_decisions": [item["body"].get("decision") for item in concurrent_responses],
                "raw_payload_logged": raw_payload_logged,
                "embedding_array_logged": embedding_array_logged,
            },
        }
        return result
    finally:
        if sampler is not None:
            sampler.stop()
        if started_container:
            _docker("stop", "--time", "10", container, check=False)
            _docker("rm", container, check=False)
        if data_dir.exists():
            shutil.rmtree(data_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before-image", required=True)
    parser.add_argument("--after-image", required=True)
    parser.add_argument("--before-commit", required=True)
    parser.add_argument("--after-commit", required=True)
    parser.add_argument("--models-dir", type=Path, required=True)
    parser.add_argument("--test-image", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path(".docker-ram-comparison"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    models_dir = args.models_dir.resolve()
    test_image = args.test_image.resolve()
    workspace = args.workspace.resolve()
    if workspace.exists():
        raise SystemExit(f"temporary workspace already exists: {workspace.name}")
    required_models = {
        "yunet": models_dir / "face_detection_yunet_2023mar.onnx",
        "arcface": models_dir / "face-recognition-resnet100-arcface.onnx",
    }
    missing = [name for name, path in required_models.items() if not path.is_file()]
    if missing:
        raise SystemExit(f"missing required models: {', '.join(missing)}")
    if not test_image.is_file():
        raise SystemExit("test image is unavailable")

    token = secrets.token_urlsafe(32)
    encryption_key = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii")
    environment = {
        "ALLOW_LEGACY_DEVICE_ID_ONLY": "true",
        "ALLOW_LEGACY_SINGLE_IMAGE_VERIFICATION": "true",
        "API_BEARER_TOKEN": token,
        "APP_REPLICA_COUNT": "1",
        "ARCFACE_MODEL_PATH": "/app/models/face-recognition-resnet100-arcface.onnx",
        "BIOMETRIC_ENCRYPTION_KEY": encryption_key,
        "DATABASE_AUTO_CREATE": "true",
        "DETECTOR_PROVIDER": "yunet",
        "DEVICE_PROOF_REQUIRED": "false",
        "ENABLE_API_DOCS": "false",
        "ENVIRONMENT": "development",
        "ESS_DATABASE_PATH": "/app/data/ess.sqlite3",
        "FACE_INFERENCE_CONCURRENCY": "2",
        "FACE_REGISTER_LIMIT_PER_HOUR": "1000",
        "FACE_VERIFY_LIMIT_PER_MINUTE": "1000",
        "LIVENESS_REQUIRED": "false",
        "LOW_LEVEL_FACE_LIMIT_PER_MINUTE": "1000",
        "ONNX_PROVIDERS": "CPUExecutionProvider",
        "ORT_INTER_OP_THREADS": "1",
        "ORT_INTRA_OP_THREADS": "2",
        "RATE_LIMIT_BACKEND": "memory",
        "RECOGNIZER_PROVIDER": "arcface_onnx",
        "REQUIRE_CALIBRATION": "false",
        "YUNET_MODEL_PATH": "/app/models/face_detection_yunet_2023mar.onnx",
    }
    safe_environment_fingerprint = hashlib.sha256(
        json.dumps(environment, sort_keys=True).encode("utf-8")
    ).hexdigest()
    payload = _image_payload(test_image)
    workspace.mkdir(parents=True)
    try:
        before = _run_case(
            label="before", image=args.before_image, commit=args.before_commit,
            models_dir=models_dir, data_dir=workspace / "before-data",
            image_payload=payload, environment=environment,
        )
        after = _run_case(
            label="after", image=args.after_image, commit=args.after_commit,
            models_dir=models_dir, data_dir=workspace / "after-data",
            image_payload=payload, environment=environment,
        )
        results = {
            "method": {
                "description": "production-style local Docker comparison",
                "cpu_limit": float(CPU_LIMIT),
                "memory_limit_mib": 2048,
                "host_port": HOST_PORT,
                "sample_interval_ms": SAMPLE_INTERVAL_SECONDS * 1000,
                "environment_fingerprint": safe_environment_fingerprint,
                "test_image_sha256": _sha256(test_image),
                "model_sha256": {name: _sha256(path) for name, path in required_models.items()},
            },
            "before": before,
            "after": after,
        }
        args.output.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(results, indent=2, sort_keys=True))
    finally:
        if workspace.exists():
            shutil.rmtree(workspace)


if __name__ == "__main__":
    main()
