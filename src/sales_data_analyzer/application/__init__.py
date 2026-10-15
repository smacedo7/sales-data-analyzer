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
from .workspace import CompanyWorkspace, ImportSummary, ItemInput

__all__ = [
    "ApplicationError",
    "CatalogConflictError",
    "CompanyNotFoundError",
    "CompanyWorkspace",
    "DuplicateCompanyError",
    "DuplicateProductError",
    "DuplicateSaleError",
    "EmptySaleError",
    "ImportSummary",
    "InsufficientHistoryError",
    "InvalidPeriodError",
    "ItemInput",
    "NoCompanySelectedError",
    "NoSalesInSelectionError",
    "SalesSession",
    "Selection",
    "TimestampAwarenessError",
    "UnknownProductError",
]
