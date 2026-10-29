"""Temporary database files for persistence tests; never the user's real database."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
import sqlite3
import tempfile

TABLES = ("company", "product", "sale", "sale_item")


@contextmanager
def temporary_database() -> Iterator[Path]:
    """Yield a path to a not-yet-created database file inside a temporary folder."""
    with tempfile.TemporaryDirectory() as folder:
        yield Path(folder) / "sales.sqlite3"


def row_counts(path: Path) -> dict[str, int]:
    """Return the number of rows in each table, read with a separate raw connection."""
    connection = sqlite3.connect(path)
    try:
        return {
            table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in TABLES
        }
    finally:
        connection.close()


def raw_connection(path: Path) -> sqlite3.Connection:
    """Return an autocommit raw connection with foreign keys on, for arranging test data."""
    connection = sqlite3.connect(path, autocommit=True)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection
