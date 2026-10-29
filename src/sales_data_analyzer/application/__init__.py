"""Use cases that coordinate the domain for any user interface.

This layer performs no console, file-dialog or database I/O of its own, so the
terminal menu (level 2), persistence (level 3) and GUI (level 4) can share it.
Storage is reached only through the SalesRepository interface.
"""

from .errors import (
    ApplicationError,
    CatalogConflictError,
    CompanyNotFoundError,
    ConcurrentChangeError,
    DuplicateCompanyError,
    DuplicateProductError,
    DuplicateSaleError,
    EmptySaleError,
    InsufficientHistoryError,
    InvalidPeriodError,
    NoCompanySelectedError,
    NoSalesInSelectionError,
    PersistenceError,
    StorageLimitError,
    TimestampAwarenessError,
    UnknownProductError,
)
from .repository import SalesRepository, StoredCompany
from .session import SalesSession, Selection
from .workspace import CompanyWorkspace, ImportSummary, ItemInput

__all__ = [
    "ApplicationError",
    "CatalogConflictError",
    "CompanyNotFoundError",
    "CompanyWorkspace",
    "ConcurrentChangeError",
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
    "PersistenceError",
    "SalesRepository",
    "SalesSession",
    "Selection",
    "StorageLimitError",
    "StoredCompany",
    "TimestampAwarenessError",
    "UnknownProductError",
]
