import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import func, select

from app.core.config import get_settings
from app.persistence.database import database_url_from_settings
from app.persistence.schema import metadata
from app.services.ess_repository import EssRepository


def main() -> None:
    argparse.ArgumentParser(description="Verify database connectivity, schema, and aggregate table counts.").parse_args()
    settings = get_settings()
    repository = EssRepository(
        database_url_from_settings(settings), initialize=False,
        pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow,
        connect_timeout_seconds=settings.db_connect_timeout_seconds,
    )
    if not repository.ready():
        raise SystemExit("Database schema is not ready")
    with repository.database.engine.connect() as connection:
        counts = {table.name: connection.execute(select(func.count()).select_from(table)).scalar_one() for table in metadata.sorted_tables}
    print(f"Database backend: {repository.database.backend}")
    for name, count in counts.items():
        print(f"{name}: {count}")


if __name__ == "__main__":
    main()
