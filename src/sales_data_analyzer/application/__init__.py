"""Use cases that coordinate the domain for any user interface.

This layer performs no console, file-dialog or database I/O of its own, so the
terminal menu (level 2), persistence (level 3) and GUI (level 4) can share it.
"""

from .errors import (
    ApplicationError,
    CatalogConflictError,
    CompanyNotFoundError,
    DuplicateCompanyError,
    DuplicateProductError,
    DuplicateSaleError,
    EmptySaleError,
    InsufficientHistoryError,
    InvalidPeriodError,
    NoCompanySelectedError,
    NoSalesInSelectionError,
    TimestampAwarenessError,
    UnknownProductError,
)
from .session import SalesSession, Selection

__all__ = [
    "ApplicationError",
    "CatalogConflictError",
    "CompanyNotFoundError",
    "DuplicateCompanyError",
    "DuplicateProductError",
    "DuplicateSaleError",
    "EmptySaleError",
    "InsufficientHistoryError",
    "InvalidPeriodError",
    "NoCompanySelectedError",
    "NoSalesInSelectionError",
    "SalesSession",
    "Selection",
    "TimestampAwarenessError",
    "UnknownProductError",
]
