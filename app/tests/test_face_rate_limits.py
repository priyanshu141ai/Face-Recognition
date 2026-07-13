import base64
import io
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from starlette.requests import Request

from app.main import app
from app.services.abuse_control import AbuseControlService
from app.services.ess_repository import EssRepository
from app.services.rate_limit.factory import _cached
from app.services.rate_limit.memory import MemoryRateLimiter
from app.services.rate_limit.redis import RedisRateLimiter
from app.services.security_audit import SecurityAuditService


def _request(ip: str) -> Request:
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "client": (ip, 1)})


def test_ip_user_device_limits_and_independent_users(tmp_path) -> None:
    repository = EssRepository(str(tmp_path / "db.sqlite3"))
    service = AbuseControlService(
        MemoryRateLimiter(), SecurityAuditService(repository, "audit"), repository
    )
    for _ in range(2):
        service.check(
            _request("10.0.0.1"), "verify", limit=2, window_seconds=60,
            user_id="user-a", device_id="device-a",
        )
    with pytest.raises(Exception) as blocked:
        service.check(
            _request("10.0.0.1"), "verify", limit=2, window_seconds=60,
            user_id="user-a", device_id="device-a",
        )
    assert blocked.value.code == "rate_limited"
    service.check(
        _request("10.0.0.2"), "verify", limit=2, window_seconds=60,
        user_id="user-b", device_id="device-b",
    )


def test_memory_limiter_is_concurrency_safe() -> None:
    limiter = MemoryRateLimiter()
    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(lambda _: limiter.retry_after("shared", 5, 60), range(20)))
    assert sum(value is None for value in results) == 5
    assert sum(value is not None for value in results) == 15


def test_http_429_has_consistent_envelope_and_retry_after(monkeypatch, tmp_path) -> None:
    _cached.cache_clear()
    monkeypatch.setenv("API_BEARER_TOKEN", "secret")
    monkeypatch.setenv("DETECTOR_PROVIDER", "mock")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "mock")
    monkeypatch.setenv("ESS_DATABASE_PATH", str(tmp_path / "rate.sqlite3"))
    monkeypatch.setenv("LOW_LEVEL_FACE_LIMIT_PER_MINUTE", "1")
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64)).save(buffer, format="PNG")
    payload = {"image": {"kind": "base64_png", "data": base64.b64encode(buffer.getvalue()).decode("ascii")}}
    client = TestClient(app)
    client.post("/v1/faces/detect", json=payload, headers={"Authorization": "Bearer secret"})
    response = client.post("/v1/faces/detect", json=payload, headers={"Authorization": "Bearer secret"})
    assert response.status_code == 429
    assert response.headers["Retry-After"]
    assert response.json()["detail"]["code"] == "rate_limited"
    assert response.json()["detail"]["retry_after_seconds"] >= 1


@pytest.mark.skipif(not os.getenv("TEST_REDIS_URL"), reason="TEST_REDIS_URL is not configured")
def test_redis_adapter_contract() -> None:
    limiter = RedisRateLimiter(os.environ["TEST_REDIS_URL"])
    assert limiter.ping() is True
