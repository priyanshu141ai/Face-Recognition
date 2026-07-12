import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClientCodeConflictError(RuntimeError):
    pass


class FaceAlreadyRegisteredError(RuntimeError):
    pass


class DeviceAlreadyRegisteredError(RuntimeError):
    pass


class DeviceAssignedToAnotherUserError(RuntimeError):
    pass


class EssRepository:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS face_registrations (
                    user_id TEXT PRIMARY KEY,
                    encrypted_embedding BLOB NOT NULL,
                    embedding_dimension INTEGER NOT NULL,
                    detector TEXT NOT NULL,
                    recognizer TEXT NOT NULL,
                    preprocessing TEXT NOT NULL,
                    registered_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS device_registrations (
                    user_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL UNIQUE,
                    platform TEXT NOT NULL,
                    public_key TEXT,
                    registered_at TEXT NOT NULL,
                    last_verified_at TEXT
                );
                """
            )
            connection.commit()

    def create_client(self, code: str, name: str, active: bool) -> dict[str, object]:
        now = _now()
        client_id = str(uuid4())
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO clients (id, code, name, active, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (client_id, code, name, int(active), now, now),
                )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ClientCodeConflictError("Client code already exists") from exc
        return {"id": client_id, "code": code, "name": name, "active": active, "created_at": now}

    def list_clients(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, code, name, active, created_at, updated_at FROM clients ORDER BY name, code"
            ).fetchall()
        return [
            {
                "id": row["id"],
                "code": row["code"],
                "name": row["name"],
                "active": bool(row["active"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def validate_client(self, code: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, code, name FROM clients WHERE code = ? AND active = 1",
                (code,),
            ).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "code": row["code"], "name": row["name"]}

    def register_face(
        self,
        user_id: str,
        encrypted_embedding: bytes,
        embedding_dimension: int,
        detector: str,
        recognizer: str,
        preprocessing: str,
    ) -> str:
        registered_at = _now()
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO face_registrations
                        (user_id, encrypted_embedding, embedding_dimension, detector, recognizer, preprocessing, registered_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, encrypted_embedding, embedding_dimension, detector, recognizer, preprocessing, registered_at),
                )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            raise FaceAlreadyRegisteredError("A face is already registered for this user") from exc
        return registered_at

    def get_face(self, user_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT encrypted_embedding, embedding_dimension, detector, recognizer, preprocessing, registered_at
                FROM face_registrations WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def register_device(self, user_id: str, device_id: str, platform: str, public_key: str | None) -> dict[str, object]:
        now = _now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing_user = connection.execute(
                "SELECT device_id, platform, registered_at FROM device_registrations WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            if existing_user is not None:
                if existing_user["device_id"] != device_id:
                    connection.rollback()
                    raise DeviceAlreadyRegisteredError("This user is already registered to another device")
                connection.execute(
                    "UPDATE device_registrations SET platform = ?, public_key = ? WHERE user_id = ?",
                    (platform, public_key, user_id),
                )
                connection.commit()
                return {
                    "device_id": device_id,
                    "platform": platform,
                    "registered_at": existing_user["registered_at"],
                    "already_registered": True,
                }

            existing_device = connection.execute(
                "SELECT user_id FROM device_registrations WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            if existing_device is not None:
                connection.rollback()
                raise DeviceAssignedToAnotherUserError("This device is already assigned to another user")

            connection.execute(
                """
                INSERT INTO device_registrations (user_id, device_id, platform, public_key, registered_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, device_id, platform, public_key, now),
            )
            connection.commit()
        return {"device_id": device_id, "platform": platform, "registered_at": now, "already_registered": False}

    def verify_device(self, user_id: str, device_id: str) -> bool:
        now = _now()
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE device_registrations SET last_verified_at = ? WHERE user_id = ? AND device_id = ?",
                (now, user_id, device_id),
            )
            connection.commit()
            return cursor.rowcount == 1

    def get_device(self, user_id: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT device_id, platform, registered_at, last_verified_at
                FROM device_registrations WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def reset_device(self, user_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM device_registrations WHERE user_id = ?", (user_id,))
            connection.commit()
            return cursor.rowcount == 1
