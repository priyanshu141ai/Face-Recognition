import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import DateTime, func, insert, select

from app.persistence.schema import metadata
from app.services.ess_repository import EssRepository


def _datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy existing SQLite rows to an empty migrated database.")
    parser.add_argument("--source-sqlite", required=True)
    args = parser.parse_args()
    source_path = Path(args.source_sqlite).resolve()
    target_url = os.getenv("DATABASE_URL")
    if not source_path.is_file() or not target_url:
        raise SystemExit("Source SQLite file and target DATABASE_URL are required")
    repository = EssRepository(target_url, initialize=False)
    if not repository.ready():
        raise SystemExit("Target schema is not ready; run Alembic first")

    with sqlite3.connect(source_path) as source:
        source.row_factory = sqlite3.Row
        source_tables = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        with repository.database.engine.begin() as target:
            nonempty = [
                table.name for table in metadata.sorted_tables
                if target.execute(select(func.count()).select_from(table)).scalar_one()
            ]
            if nonempty:
                raise SystemExit("Target business/security tables must be empty")
            copied = {}
            for table in metadata.sorted_tables:
                if table.name not in source_tables:
                    copied[table.name] = 0
                    continue
                rows = [dict(row) for row in source.execute(f'SELECT * FROM "{table.name}"')]
                payload = []
                for row in rows:
                    value = {}
                    for column in table.columns:
                        if column.name not in row:
                            continue
                        item = row[column.name]
                        value[column.name] = _datetime(item) if isinstance(column.type, DateTime) else item
                    payload.append(value)
                if payload:
                    target.execute(insert(table), payload)
                copied[table.name] = len(payload)
    print(f"Target backend: {repository.database.backend}")
    for name, count in copied.items():
        print(f"{name}: {count}")


if __name__ == "__main__":
    main()
