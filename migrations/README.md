# Database migrations

Run `alembic upgrade head` before starting a production instance. Existing
legacy SQLite databases must be backed up, stamped at `0001_legacy_schema`, then
upgraded. Full backup, dry-run, verification, and rollback commands are in
`docs/database_migration.md`.
