# Database migration

SQLite remains supported for one-process local development and tests. PostgreSQL is required for normal staging/production. SQLAlchemy 2 Core owns repository access; Alembic owns schema changes. Routes reuse a cached repository and do not run DDL per request.

## New deployment

```powershell
$env:DATABASE_URL="postgresql+psycopg://<user>:<password>@<host>:5432/<database>"
python -m alembic upgrade head
python scripts/verify_database_migration.py
```

Run migrations as a one-time Coolify pre-deploy job before starting Uvicorn. Set `DATABASE_AUTO_CREATE=false`. `/readyz` returns 503 when the database is unreachable or required tables are absent.

## Existing SQLite database

1. Stop writes and back up the SQLite file and biometric encryption key.
2. Test the schema migration on a disposable copy:

```powershell
Copy-Item data\ess.sqlite3 data\ess.migration-test.sqlite3
$env:DATABASE_URL="sqlite:///data/ess.migration-test.sqlite3"
python -m alembic stamp 0001_legacy_schema
python -m alembic upgrade head
python scripts/verify_database_migration.py
```

Only stamp a database whose three legacy tables were created by the old repository and have been backed up; stamping does not change schema. A brand-new empty database must use `alembic upgrade head` without stamping.

3. Create an empty migrated PostgreSQL database with `alembic upgrade head`.
4. Set target `DATABASE_URL`, then run `python scripts/migrate_sqlite_to_database.py --source-sqlite data/ess.sqlite3` during the maintenance window.
5. Compare source/target aggregate counts, start the service, check `/readyz`, and run a controlled enrollment/verification smoke test.

The transfer copies encrypted template bytes without decrypting them. It never prints identifiers or biometric values. It aborts if destination business tables are not empty.

## Rollback

- Application rollback: redeploy the previous image and restore its compatible database backup.
- Schema rollback on a disposable/staging database: `python -m alembic downgrade 0001_legacy_schema`.
- Production rollback: prefer restoring the pre-migration database snapshot. Downgrade removes security tables/columns and therefore destroys their data; do not run it without an approved backup and maintenance window.

PostgreSQL backups, point-in-time recovery, credentials, TLS, monitoring, and restore drills are infrastructure responsibilities. SQLite emergency production use requires the explicit override and one replica, and is not HA.

## Biometric encryption-key rotation

Back up the database and both versioned keys, stop face writes, keep the current key/version in `BIOMETRIC_ENCRYPTION_KEY` and `BIOMETRIC_ENCRYPTION_KEY_VERSION`, and provide the new values only to the one-time job as `NEW_BIOMETRIC_ENCRYPTION_KEY` and `NEW_BIOMETRIC_ENCRYPTION_KEY_VERSION`. Run `python scripts/rotate_biometric_encryption_key.py`. It decrypts all candidates before one update transaction and prints only an aggregate count. Then deploy the new key/version and verify readiness plus a controlled face check. Do not discard the old key until backup retention and rollback windows close.
