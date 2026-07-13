from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from app.core.config import Settings
from app.persistence.schema import metadata


def normalize_database_url(value: str) -> str:
    if value == ":memory:":
        return "sqlite+pysqlite://"
    if "://" in value:
        return value
    path = Path(value).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+pysqlite:///{path.as_posix()}"


def database_url_from_settings(settings: Settings) -> str:
    return normalize_database_url(settings.database_url or settings.ess_database_path)


class Database:
    def __init__(
        self,
        url: str,
        *,
        pool_size: int = 5,
        max_overflow: int = 10,
        connect_timeout_seconds: int = 10,
    ) -> None:
        self.url = normalize_database_url(url)
        kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if self.url.startswith("sqlite"):
            kwargs["connect_args"] = {
                "check_same_thread": False,
                "timeout": connect_timeout_seconds,
            }
            if self.url == "sqlite+pysqlite://":
                kwargs["poolclass"] = StaticPool
        else:
            kwargs.update(pool_size=pool_size, max_overflow=max_overflow)
            kwargs["connect_args"] = {"connect_timeout": connect_timeout_seconds}
        self.engine: Engine = create_engine(self.url, **kwargs)
        if self.url.startswith("sqlite"):
            @event.listens_for(self.engine, "connect")
            def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

    @property
    def backend(self) -> str:
        return self.engine.url.get_backend_name()

    def create_schema(self) -> None:
        metadata.create_all(self.engine)

    def ping(self) -> bool:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    def validate_schema(self) -> bool:
        inspector = inspect(self.engine)
        present = set(inspector.get_table_names())
        required = {table.name for table in metadata.sorted_tables}
        if not required.issubset(present):
            return False
        return all(
            {column.name for column in table.columns}.issubset(
                {column["name"] for column in inspector.get_columns(table.name)}
            )
            for table in metadata.sorted_tables
        )

    def dispose(self) -> None:
        self.engine.dispose()
