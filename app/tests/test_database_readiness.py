from fastapi.testclient import TestClient

from app.main import app


def test_database_failure_makes_readiness_503_without_url_disclosure(monkeypatch) -> None:
    url = "postgresql+psycopg://invalid:invalid@127.0.0.1:1/unavailable"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("DATABASE_AUTO_CREATE", "false")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT_SECONDS", "1")
    monkeypatch.setenv("DETECTOR_PROVIDER", "mock")
    monkeypatch.setenv("RECOGNIZER_PROVIDER", "mock")
    response = TestClient(app).get("/readyz")
    assert response.status_code == 503
    assert url not in response.text
