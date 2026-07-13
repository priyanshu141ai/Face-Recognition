import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.services.ess_repository import EssRepository, FaceAlreadyRegisteredError


def _config(path) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path.as_posix()}")
    return config


def test_legacy_schema_upgrades_and_rolls_back(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    database = tmp_path / "migration.sqlite3"
    config = _config(database)
    command.upgrade(config, "0001_legacy_schema")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO device_registrations "
            "(user_id,device_id,platform,public_key,registered_at,last_verified_at) "
            "VALUES (?,?,?,?,?,?)",
            ("user-a", "phone-001", "android", None, "2026-01-01T00:00:00+00:00", None),
        )
    command.upgrade(config, "head")
    assert EssRepository(str(database), initialize=False).ready() is True
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT key_version FROM device_registrations WHERE user_id='user-a'"
        ).fetchone()[0] == 1
        face_columns = {row[1] for row in connection.execute("PRAGMA table_info(face_registrations)")}
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"capture_count", "captured_angles", "template_version"} <= face_columns
    assert {"liveness_challenges", "device_challenges", "security_audit_events"} <= tables
    command.downgrade(config, "0001_legacy_schema")
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(device_registrations)")}
        face_columns = {row[1] for row in connection.execute("PRAGMA table_info(face_registrations)")}
    assert "key_version" not in columns
    assert "capture_count" not in face_columns


def test_duplicate_enrollment_and_challenge_consumption_are_atomic(tmp_path) -> None:
    repository = EssRepository(str(tmp_path / "race.sqlite3"))

    def enroll(_):
        try:
            repository.register_face("user-a", b"encrypted", 1, "detector", "recognizer", "preprocess")
            return True
        except FaceAlreadyRegisteredError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(enroll, range(8))) == 1

    from app.services.device_proof import DeviceProofService

    challenge = DeviceProofService(repository, 60).issue("user-a", "phone-001", "register")
    with ThreadPoolExecutor(max_workers=8) as executor:
        consumed = list(executor.map(
            lambda _: repository.consume_device_challenge(challenge.challenge_id), range(8)
        ))
    assert sum(consumed) == 1


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL is not configured")
def test_postgres_repository_contract() -> None:
    repository = EssRepository(os.environ["TEST_POSTGRES_URL"])
    assert repository.ready() is True
    repository.database.dispose()
