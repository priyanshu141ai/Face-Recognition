from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from app.persistence.database import Database
from app.persistence.schema import (
    clients,
    device_challenges,
    device_registrations,
    face_registrations,
    liveness_challenges,
    replay_records,
    security_attempts,
    security_audit_events,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ClientCodeConflictError(RuntimeError):
    pass


class FaceAlreadyRegisteredError(RuntimeError):
    pass


class DeviceAlreadyRegisteredError(RuntimeError):
    pass


class DeviceAssignedToAnotherUserError(RuntimeError):
    pass


class DeviceKeyConflictError(RuntimeError):
    pass


class EssRepository:
    """SQLAlchemy Core repository usable with SQLite and PostgreSQL.

    Direct construction auto-creates tables for local/tests. Production routes pass
    ``initialize=False`` and require Alembic migrations before readiness succeeds.
    """

    def __init__(
        self,
        database_path_or_url: str,
        *,
        initialize: bool = True,
        pool_size: int = 5,
        max_overflow: int = 10,
        connect_timeout_seconds: int = 10,
    ) -> None:
        self.database_path = database_path_or_url
        self.database = Database(
            database_path_or_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            connect_timeout_seconds=connect_timeout_seconds,
        )
        if initialize:
            self.initialize()

    def initialize(self) -> None:
        self.database.create_schema()

    def ready(self) -> bool:
        return self.database.ping() and self.database.validate_schema()

    def create_client(self, code: str, name: str, active: bool) -> dict[str, object]:
        now, client_id = _now(), str(uuid4())
        values = {
            "id": client_id,
            "code": code,
            "name": name,
            "active": active,
            "created_at": now,
            "updated_at": now,
        }
        try:
            with self.database.engine.begin() as connection:
                connection.execute(insert(clients).values(**values))
        except IntegrityError as exc:
            raise ClientCodeConflictError("Client code already exists") from exc
        return values

    def list_clients(self) -> list[dict[str, object]]:
        statement = select(clients).order_by(clients.c.name, clients.c.code)
        with self.database.engine.connect() as connection:
            rows = connection.execute(statement).mappings().all()
        return [dict(row) for row in rows]

    def validate_client(self, code: str) -> dict[str, object] | None:
        statement = select(clients.c.id, clients.c.code, clients.c.name).where(
            and_(clients.c.code == code, clients.c.active.is_(True))
        )
        with self.database.engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return dict(row) if row else None

    def register_face(
        self,
        user_id: str,
        encrypted_embedding: bytes,
        embedding_dimension: int,
        detector: str,
        recognizer: str,
        preprocessing: str,
        *,
        encryption_key_version: int = 1,
        consent_reference: str | None = None,
        calibration_version: str | None = None,
        capture_count: int = 1,
        captured_angles: str = "legacy",
        template_version: str = "single_capture_v1",
    ) -> datetime:
        now = _now()
        try:
            with self.database.engine.begin() as connection:
                existing = connection.execute(select(face_registrations).where(
                    face_registrations.c.user_id == user_id
                )).mappings().first()
                values = dict(
                    encrypted_embedding=encrypted_embedding,
                    embedding_dimension=embedding_dimension,
                    detector=detector,
                    recognizer=recognizer,
                    preprocessing=preprocessing,
                    registered_at=now,
                    updated_at=now,
                    encryption_key_version=encryption_key_version,
                    consent_reference=consent_reference,
                    calibration_version=calibration_version,
                    capture_count=capture_count,
                    captured_angles=captured_angles,
                    template_version=template_version,
                )
                if existing:
                    if existing["revoked_at"] is None and existing["deleted_at"] is None:
                        raise FaceAlreadyRegisteredError("A face is already registered for this user")
                    connection.execute(update(face_registrations).where(
                        face_registrations.c.user_id == user_id
                    ).values(**values, revoked_at=None, deleted_at=None))
                else:
                    connection.execute(insert(face_registrations).values(user_id=user_id, **values))
        except FaceAlreadyRegisteredError:
            raise
        except IntegrityError as exc:
            raise FaceAlreadyRegisteredError("A face is already registered for this user") from exc
        return now

    def get_face(self, user_id: str) -> dict[str, object] | None:
        statement = select(face_registrations).where(and_(
            face_registrations.c.user_id == user_id,
            face_registrations.c.revoked_at.is_(None),
            face_registrations.c.deleted_at.is_(None),
        ))
        with self.database.engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return dict(row) if row else None

    def get_face_status(self, user_id: str) -> dict[str, object] | None:
        with self.database.engine.connect() as connection:
            row = connection.execute(select(face_registrations).where(
                face_registrations.c.user_id == user_id
            )).mappings().first()
        return dict(row) if row else None

    def revoke_face(self, user_id: str) -> bool:
        with self.database.engine.begin() as connection:
            result = connection.execute(update(face_registrations).where(
                face_registrations.c.user_id == user_id
            ).values(revoked_at=_now(), updated_at=_now()))
        return result.rowcount == 1

    def delete_face(self, user_id: str) -> bool:
        now = _now()
        with self.database.engine.begin() as connection:
            result = connection.execute(update(face_registrations).where(
                face_registrations.c.user_id == user_id
            ).values(
                encrypted_embedding=b"",
                embedding_dimension=0,
                deleted_at=now,
                revoked_at=now,
                updated_at=now,
            ))
        return result.rowcount == 1

    def rotate_face_encryption(
        self, user_id: str, encrypted_embedding: bytes, encryption_key_version: int
    ) -> bool:
        with self.database.engine.begin() as connection:
            result = connection.execute(update(face_registrations).where(and_(
                face_registrations.c.user_id == user_id,
                face_registrations.c.deleted_at.is_(None),
            )).values(
                encrypted_embedding=encrypted_embedding,
                encryption_key_version=encryption_key_version,
                updated_at=_now(),
            ))
        return result.rowcount == 1

    def register_device(
        self,
        user_id: str,
        device_id: str,
        platform: str,
        public_key: str | None,
        *,
        public_key_fingerprint: str | None = None,
        key_algorithm: str | None = None,
    ) -> dict[str, object]:
        now = _now()
        with self.database.engine.begin() as connection:
            existing_user = connection.execute(select(device_registrations).where(
                device_registrations.c.user_id == user_id
            )).mappings().first()
            if existing_user and existing_user["revoked_at"] is None:
                if existing_user["device_id"] != device_id:
                    raise DeviceAlreadyRegisteredError("This user is already registered to another device")
                if (
                    existing_user["public_key_fingerprint"]
                    and public_key_fingerprint
                    and existing_user["public_key_fingerprint"] != public_key_fingerprint
                ):
                    raise DeviceKeyConflictError("Use the key-rotation flow to change the device key")
                connection.execute(update(device_registrations).where(
                    device_registrations.c.user_id == user_id
                ).values(platform=platform, updated_at=now))
                return {
                    "device_id": device_id,
                    "platform": platform,
                    "registered_at": existing_user["registered_at"],
                    "already_registered": True,
                    "key_version": existing_user["key_version"],
                }

            existing_device = connection.execute(select(device_registrations.c.user_id).where(and_(
                device_registrations.c.device_id == device_id,
                device_registrations.c.revoked_at.is_(None),
            ))).first()
            if existing_device and existing_device[0] != user_id:
                raise DeviceAssignedToAnotherUserError("This device is already assigned to another user")

            if existing_user:
                connection.execute(update(device_registrations).where(
                    device_registrations.c.user_id == user_id
                ).values(
                    device_id=device_id,
                    platform=platform,
                    public_key=public_key,
                    public_key_fingerprint=public_key_fingerprint,
                    key_algorithm=key_algorithm,
                    key_version=int(existing_user["key_version"] or 0) + 1,
                    registered_at=now,
                    updated_at=now,
                    revoked_at=None,
                    last_verified_at=None,
                ))
                key_version = int(existing_user["key_version"] or 0) + 1
            else:
                connection.execute(insert(device_registrations).values(
                    user_id=user_id,
                    device_id=device_id,
                    platform=platform,
                    public_key=public_key,
                    public_key_fingerprint=public_key_fingerprint,
                    key_algorithm=key_algorithm,
                    key_version=1,
                    registered_at=now,
                    updated_at=now,
                ))
                key_version = 1
        return {
            "device_id": device_id,
            "platform": platform,
            "registered_at": now,
            "already_registered": False,
            "key_version": key_version,
        }

    def is_device_bound(self, user_id: str, device_id: str) -> bool:
        statement = select(device_registrations.c.user_id).where(and_(
            device_registrations.c.user_id == user_id,
            device_registrations.c.device_id == device_id,
            device_registrations.c.revoked_at.is_(None),
        ))
        with self.database.engine.connect() as connection:
            return connection.execute(statement).first() is not None

    def verify_device(self, user_id: str, device_id: str) -> bool:
        with self.database.engine.begin() as connection:
            result = connection.execute(update(device_registrations).where(and_(
                device_registrations.c.user_id == user_id,
                device_registrations.c.device_id == device_id,
                device_registrations.c.revoked_at.is_(None),
            )).values(last_verified_at=_now()))
        return result.rowcount == 1

    def get_device(self, user_id: str) -> dict[str, object] | None:
        statement = select(
            device_registrations.c.device_id,
            device_registrations.c.platform,
            device_registrations.c.registered_at,
            device_registrations.c.last_verified_at,
            device_registrations.c.key_version,
            device_registrations.c.key_algorithm,
        ).where(and_(
            device_registrations.c.user_id == user_id,
            device_registrations.c.revoked_at.is_(None),
        ))
        with self.database.engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return dict(row) if row else None

    def get_device_security(self, user_id: str, device_id: str) -> dict[str, object] | None:
        statement = select(device_registrations).where(and_(
            device_registrations.c.user_id == user_id,
            device_registrations.c.device_id == device_id,
            device_registrations.c.revoked_at.is_(None),
        ))
        with self.database.engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return dict(row) if row else None

    def get_device_security_state(self, user_id: str, device_id: str) -> dict[str, object] | None:
        statement = select(device_registrations).where(and_(
            device_registrations.c.user_id == user_id,
            device_registrations.c.device_id == device_id,
        ))
        with self.database.engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
        return dict(row) if row else None

    def rotate_device_key(
        self,
        user_id: str,
        device_id: str,
        public_key: str,
        fingerprint: str,
        algorithm: str,
    ) -> int | None:
        record = self.get_device_security(user_id, device_id)
        if not record:
            return None
        version = int(record["key_version"] or 0) + 1
        try:
            with self.database.engine.begin() as connection:
                connection.execute(update(device_registrations).where(and_(
                    device_registrations.c.user_id == user_id,
                    device_registrations.c.device_id == device_id,
                    device_registrations.c.revoked_at.is_(None),
                )).values(
                    public_key=public_key,
                    public_key_fingerprint=fingerprint,
                    key_algorithm=algorithm,
                    key_version=version,
                    updated_at=_now(),
                ))
        except IntegrityError as exc:
            raise DeviceKeyConflictError("This public key is already registered") from exc
        return version

    def revoke_device(self, user_id: str, device_id: str) -> bool:
        with self.database.engine.begin() as connection:
            result = connection.execute(update(device_registrations).where(and_(
                device_registrations.c.user_id == user_id,
                device_registrations.c.device_id == device_id,
                device_registrations.c.revoked_at.is_(None),
            )).values(revoked_at=_now(), updated_at=_now()))
        return result.rowcount == 1

    def reset_device(self, user_id: str) -> bool:
        with self.database.engine.begin() as connection:
            result = connection.execute(delete(device_registrations).where(
                device_registrations.c.user_id == user_id
            ))
        return result.rowcount == 1

    def create_liveness_challenge(self, **values: object) -> None:
        with self.database.engine.begin() as connection:
            connection.execute(insert(liveness_challenges).values(**values))

    def get_liveness_challenge(self, challenge_id: str) -> dict[str, object] | None:
        with self.database.engine.connect() as connection:
            row = connection.execute(select(liveness_challenges).where(
                liveness_challenges.c.challenge_id == challenge_id
            )).mappings().first()
        return dict(row) if row else None

    def increment_liveness_attempt(self, challenge_id: str, status: str = "attempted") -> int:
        with self.database.engine.begin() as connection:
            connection.execute(update(liveness_challenges).where(
                liveness_challenges.c.challenge_id == challenge_id
            ).values(
                attempt_count=liveness_challenges.c.attempt_count + 1,
                status=status,
            ))
            count = connection.execute(select(liveness_challenges.c.attempt_count).where(
                liveness_challenges.c.challenge_id == challenge_id
            )).scalar_one()
        return int(count)

    def consume_liveness_challenge(self, challenge_id: str) -> bool:
        with self.database.engine.begin() as connection:
            result = connection.execute(update(liveness_challenges).where(and_(
                liveness_challenges.c.challenge_id == challenge_id,
                liveness_challenges.c.used_at.is_(None),
            )).values(used_at=_now(), status="used"))
        return result.rowcount == 1

    def create_device_challenge(self, **values: object) -> None:
        with self.database.engine.begin() as connection:
            connection.execute(insert(device_challenges).values(**values))

    def get_device_challenge(self, challenge_id: str) -> dict[str, object] | None:
        with self.database.engine.connect() as connection:
            row = connection.execute(select(device_challenges).where(
                device_challenges.c.challenge_id == challenge_id
            )).mappings().first()
        return dict(row) if row else None

    def consume_device_challenge(self, challenge_id: str) -> bool:
        with self.database.engine.begin() as connection:
            result = connection.execute(update(device_challenges).where(and_(
                device_challenges.c.challenge_id == challenge_id,
                device_challenges.c.used_at.is_(None),
            )).values(used_at=_now(), status="used"))
        return result.rowcount == 1

    def claim_replay_record(
        self,
        scope_hash: str,
        fingerprint: str,
        kind: str,
        expires_at: datetime,
    ) -> bool:
        now = _now()
        try:
            with self.database.engine.begin() as connection:
                connection.execute(delete(replay_records).where(replay_records.c.expires_at <= now))
                connection.execute(insert(replay_records).values(
                    id=str(uuid4()),
                    scope_hash=scope_hash,
                    fingerprint=fingerprint,
                    kind=kind,
                    created_at=now,
                    expires_at=expires_at,
                ))
            return True
        except IntegrityError:
            return False

    def claim_replay_records(
        self,
        scope_hash: str,
        claims: list[tuple[str, str]],
        expires_at: datetime,
    ) -> bool:
        if len(set(claims)) != len(claims):
            return False
        now = _now()
        try:
            with self.database.engine.begin() as connection:
                connection.execute(delete(replay_records).where(replay_records.c.expires_at <= now))
                connection.execute(insert(replay_records), [
                    {
                        "id": str(uuid4()), "scope_hash": scope_hash,
                        "fingerprint": fingerprint, "kind": kind,
                        "created_at": now, "expires_at": expires_at,
                    }
                    for fingerprint, kind in claims
                ])
            return True
        except IntegrityError:
            return False

    def get_security_attempt(self, scope_hash: str, action: str) -> dict[str, object] | None:
        with self.database.engine.connect() as connection:
            row = connection.execute(select(security_attempts).where(and_(
                security_attempts.c.scope_hash == scope_hash,
                security_attempts.c.action == action,
            ))).mappings().first()
        return dict(row) if row else None

    def save_security_attempt(self, scope_hash: str, action: str, **values: object) -> None:
        now = _now()
        with self.database.engine.begin() as connection:
            existing = connection.execute(select(security_attempts.c.id).where(and_(
                security_attempts.c.scope_hash == scope_hash,
                security_attempts.c.action == action,
            ))).first()
            payload = {**values, "updated_at": now}
            if existing:
                connection.execute(update(security_attempts).where(
                    security_attempts.c.id == existing[0]
                ).values(**payload))
            else:
                connection.execute(insert(security_attempts).values(
                    id=str(uuid4()), scope_hash=scope_hash, action=action, **payload
                ))

    def clear_security_attempt(self, scope_hash: str, action: str) -> None:
        with self.database.engine.begin() as connection:
            connection.execute(delete(security_attempts).where(and_(
                security_attempts.c.scope_hash == scope_hash,
                security_attempts.c.action == action,
            )))

    def append_audit_event(
        self,
        event_type: str,
        outcome: str,
        *,
        subject_hash: str | None = None,
        device_hash: str | None = None,
        request_id: str | None = None,
        reason_code: str | None = None,
    ) -> None:
        with self.database.engine.begin() as connection:
            connection.execute(insert(security_audit_events).values(
                id=str(uuid4()),
                event_type=event_type,
                subject_hash=subject_hash,
                device_hash=device_hash,
                request_id=request_id,
                outcome=outcome,
                reason_code=reason_code,
                created_at=_now(),
            ))


@lru_cache(maxsize=64)
def cached_repository(
    database_url: str,
    initialize: bool,
    pool_size: int,
    max_overflow: int,
    connect_timeout_seconds: int,
) -> EssRepository:
    return EssRepository(
        database_url,
        initialize=initialize,
        pool_size=pool_size,
        max_overflow=max_overflow,
        connect_timeout_seconds=connect_timeout_seconds,
    )
