"""Thread-local SQLite connections with WAL mode and idempotent schema deployment."""

from __future__ import annotations

import logging
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from backend.config import get_config

logger = logging.getLogger(__name__)

_local = threading.local()
_SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def get_db_path() -> Path:
    """Return the database file path, creating the parent directory if needed."""
    config = get_config()
    config.database.db_dir.mkdir(parents=True, exist_ok=True)
    return config.database.db_path


def _init_connection(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Thread-local connection. One connection per thread, reused.

    Pass db_path=":memory:" for testing.
    """
    key = str(db_path) if db_path else "_default"
    connections: dict[str, sqlite3.Connection] = getattr(_local, "connections", {})

    if key not in connections:
        path = str(db_path) if db_path else str(get_db_path())
        conn = sqlite3.connect(path)
        _init_connection(conn)
        connections[key] = conn
        _local.connections = connections

    return connections[key]


@contextmanager
def get_transaction(
    db_path: str | Path | None = None,
) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that commits on success, rolls back on exception."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def deploy_schema(db_path: str | Path | None = None) -> None:
    """Idempotent schema deployment from schema.sql.

    All statements use IF NOT EXISTS so this is safe to call on every startup.
    """
    schema_sql = _SCHEMA_FILE.read_text()
    conn = get_connection(db_path)
    conn.executescript(schema_sql)
    logger.info("Schema deployed (or already current)")


def close_connection(db_path: str | Path | None = None) -> None:
    """Close the thread-local connection. Call during cleanup."""
    key = str(db_path) if db_path else "_default"
    connections: dict[str, sqlite3.Connection] = getattr(_local, "connections", {})
    conn = connections.pop(key, None)
    if conn:
        conn.close()
