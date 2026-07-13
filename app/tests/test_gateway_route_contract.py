from fastapi.testclient import TestClient

from app.api.dependencies import repository_dependency
from app.main import app
from app.tests.gateway_test_utils import TestGatewaySigner


def _secure_environment(monkeypatch, tmp_path, signer):
    jwks = tmp_path / "route-public.jwks.json"
    signer.write_public_jwks(jwks)
    monkeypatch.setenv("API_BEARER_TOKEN", "service-test-token")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'route.sqlite3').as_posix()}")
    monkeypatch.setenv("DATABASE_AUTO_CREATE", "true")
    monkeypatch.setenv("GATEWAY_ASSERTION_REQUIRED", "true")
    monkeypatch.setenv("ALLOW_UNSIGNED_IDENTITY_HEADERS", "false")
    monkeypatch.setenv("GATEWAY_ASSERTION_ISSUER", "https://gateway.test")
    monkeypatch.setenv("GATEWAY_ASSERTION_AUDIENCE", "face-api-test")
    monkeypatch.setenv("GATEWAY_ALLOWED_TENANTS", "tenant-001")
    monkeypatch.setenv("GATEWAY_JWKS_PATH", str(jwks))
    monkeypatch.setenv("AUDIT_HASH_KEY", "audit-test-key")


def _headers(signer, request_id, device_id="device-0001", key_version=1):
    token = signer.sign(
        action="device_status", path="/api/ess/device/status", request_id=request_id,
        device_id=device_id, device_key_version=key_version,
    )
    return {
        "Authorization": "Bearer service-test-token",
        "X-Gateway-Assertion": token,
        "X-Request-ID": request_id,
    }


def test_direct_identity_headers_are_rejected_but_public_routes_remain_public(monkeypatch, tmp_path) -> None:
    signer = TestGatewaySigner()
    _secure_environment(monkeypatch, tmp_path, signer)
    client = TestClient(app)
    response = client.get(
        "/api/ess/device/status",
        headers={"Authorization": "Bearer service-test-token", "X-User-ID": "user-001"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "gateway_assertion_missing"
    assert client.get("/healthz").status_code == 200


def test_three_angle_registration_does_not_trust_raw_identity_headers(monkeypatch, tmp_path) -> None:
    signer = TestGatewaySigner()
    _secure_environment(monkeypatch, tmp_path, signer)
    payload = {
        "enrollment_images": [
            {"angle": angle, "image": {"kind": "base64_png", "data": "AA=="}}
            for angle in ("front", "left", "right")
        ]
    }
    response = TestClient(app).post(
        "/api/ess/face/register",
        json=payload,
        headers={"Authorization": "Bearer service-test-token", "X-User-ID": "user-001"},
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "gateway_assertion_missing"


def test_one_device_login_status_uses_signed_candidate_device(monkeypatch, tmp_path) -> None:
    signer = TestGatewaySigner()
    _secure_environment(monkeypatch, tmp_path, signer)
    client = TestClient(app)

    response = client.get("/api/ess/device/status", headers=_headers(signer, "status-new", key_version=0))
    assert response.status_code == 200
    assert response.json()["session_state"] == "registration_required"

    repository = repository_dependency()
    repository.register_device("user-001", "device-0001", "android", None)
    active = client.get("/api/ess/device/status", headers=_headers(signer, "status-active"))
    assert active.status_code == 200
    assert active.json()["session_state"] == "active"

    changed = client.get(
        "/api/ess/device/status",
        headers=_headers(signer, "status-changed", device_id="device-0002"),
    )
    assert changed.status_code == 200
    assert changed.json()["session_state"] == "device_change_required"


def test_compatibility_header_must_match_signed_identity(monkeypatch, tmp_path) -> None:
    signer = TestGatewaySigner()
    _secure_environment(monkeypatch, tmp_path, signer)
    headers = {**_headers(signer, "status-mismatch", key_version=0), "X-User-ID": "other-user"}
    response = TestClient(app).get("/api/ess/device/status", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "gateway_user_mismatch"

    headers = {**_headers(signer, "device-mismatch", key_version=0), "X-Device-ID": "device-9999"}
    response = TestClient(app).get("/api/ess/device/status", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "gateway_device_mismatch"


def test_bearer_and_assertion_layers_are_both_required(monkeypatch, tmp_path) -> None:
    signer = TestGatewaySigner()
    _secure_environment(monkeypatch, tmp_path, signer)
    headers = _headers(signer, "layered-auth", key_version=0)
    headers["Authorization"] = "Bearer wrong-token"
    assert TestClient(app).get("/api/ess/device/status", headers=headers).status_code == 401
    invalid = {
        "Authorization": "Bearer service-test-token",
        "X-Gateway-Assertion": "malformed-test-assertion",
        "X-Request-ID": "invalid-assertion",
    }
    response = TestClient(app).get("/api/ess/device/status", headers=invalid)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "gateway_assertion_invalid"


def test_unsigned_identity_compatibility_requires_explicit_development_flag(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("API_BEARER_TOKEN", "service-test-token")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'compat.sqlite3').as_posix()}")
    monkeypatch.setenv("DATABASE_AUTO_CREATE", "true")
    monkeypatch.setenv("GATEWAY_ASSERTION_REQUIRED", "false")
    monkeypatch.setenv("ALLOW_UNSIGNED_IDENTITY_HEADERS", "true")
    response = TestClient(app).get(
        "/api/ess/device/status",
        headers={"Authorization": "Bearer service-test-token", "X-User-ID": "user-001"},
    )
    assert response.status_code == 200


def test_openapi_requires_bearer_and_gateway_assertion_together() -> None:
    schema = app.openapi()
    schemes = schema["components"]["securitySchemes"]
    assert {"ServiceBearer", "GatewayAssertion"}.issubset(schemes)
    assert schema["paths"]["/api/ess/device/status"]["get"]["security"] == [
        {"ServiceBearer": [], "GatewayAssertion": []}
    ]
    assert "security" not in schema["paths"]["/healthz"]["get"]


def test_all_protected_openapi_operations_keep_bearer_and_gateway_security() -> None:
    schema = app.openapi()
    public = {"/", "/healthz", "/readyz", "/api/public/clients/validate"}
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if path in public:
                assert "security" not in operation
            else:
                assert operation.get("security") == [{"ServiceBearer": [], "GatewayAssertion": []}]


def test_readiness_fails_when_required_public_jwks_is_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GATEWAY_ASSERTION_REQUIRED", "true")
    monkeypatch.setenv("GATEWAY_ASSERTION_ISSUER", "https://gateway.test")
    monkeypatch.setenv("GATEWAY_ASSERTION_AUDIENCE", "face-api-test")
    monkeypatch.setenv("GATEWAY_ALLOWED_TENANTS", "tenant-001")
    monkeypatch.setenv("GATEWAY_JWKS_PATH", str(tmp_path / "missing.jwks.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'ready.sqlite3').as_posix()}")
    monkeypatch.setenv("DATABASE_AUTO_CREATE", "true")
    response = TestClient(app).get("/readyz")
    assert response.status_code == 503
    assert response.json()["reason"] == "dependency_initialization_failed"
