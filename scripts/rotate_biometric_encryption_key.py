import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import and_, select, update

from app.core.config import get_settings
from app.persistence.database import database_url_from_settings
from app.persistence.schema import face_registrations
from app.services.ess_repository import EssRepository


def main() -> None:
    settings = get_settings()
    old_value = settings.biometric_encryption_key
    new_value = os.getenv("NEW_BIOMETRIC_ENCRYPTION_KEY")
    new_version_value = os.getenv("NEW_BIOMETRIC_ENCRYPTION_KEY_VERSION")
    if not old_value or not new_value or not new_version_value:
        raise SystemExit("Current/new biometric keys and NEW_BIOMETRIC_ENCRYPTION_KEY_VERSION are required")
    new_version = int(new_version_value)
    if new_version <= settings.biometric_encryption_key_version:
        raise SystemExit("New key version must be greater than the current version")
    try:
        old_cipher, new_cipher = Fernet(old_value.encode()), Fernet(new_value.encode())
    except (ValueError, TypeError) as exc:
        raise SystemExit("Biometric key configuration is invalid") from exc
    repository = EssRepository(database_url_from_settings(settings), initialize=False)
    with repository.database.engine.connect() as connection:
        rows = connection.execute(select(
            face_registrations.c.user_id,
            face_registrations.c.encrypted_embedding,
            face_registrations.c.encryption_key_version,
        ).where(face_registrations.c.deleted_at.is_(None))).mappings().all()
    unknown_versions = {
        int(row["encryption_key_version"]) for row in rows
        if int(row["encryption_key_version"]) not in {settings.biometric_encryption_key_version, new_version}
    }
    if unknown_versions:
        raise SystemExit("Database contains unsupported biometric key versions")
    rotated = []
    try:
        for row in rows:
            if int(row["encryption_key_version"]) == new_version:
                continue
            rotated.append((row["user_id"], new_cipher.encrypt(old_cipher.decrypt(row["encrypted_embedding"]))))
    except InvalidToken as exc:
        raise SystemExit("A template could not be decrypted; no database changes were made") from exc
    with repository.database.engine.begin() as connection:
        for user_id, encrypted in rotated:
            connection.execute(update(face_registrations).where(and_(
                face_registrations.c.user_id == user_id,
                face_registrations.c.encryption_key_version == settings.biometric_encryption_key_version,
            )).values(encrypted_embedding=encrypted, encryption_key_version=new_version))
    print(f"Rotated encrypted biometric templates: {len(rotated)}")


if __name__ == "__main__":
    main()
