"""SQLite persistence adapter implementing the application's SalesRepository."""

from .schema import APPLICATION_ID, SCHEMA_VERSION
from .sqlite import (
    CorruptDataError,
    DatabaseOpenError,
    SQLiteSalesRepository,
    default_database_path,
)

__all__ = [
    "APPLICATION_ID",
    "SCHEMA_VERSION",
    "CorruptDataError",
    "DatabaseOpenError",
    "SQLiteSalesRepository",
    "default_database_path",
]
