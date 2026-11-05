"""Qt-free wording of failures shown by the desktop window (one error funnel).

Order matters: specific subclasses are tested before their ValueError bases, so
the window words every refusal exactly like the terminal menu does.
"""

from sales_data_analyzer.application import (
    ApplicationError,
    ConcurrentChangeError,
    InsufficientHistoryError,
    NoSalesInSelectionError,
    PersistenceError,
    StorageLimitError,
)
from sales_data_analyzer.charts.images import ChartWriteError
from sales_data_analyzer.cli.formatting import (
    describe_import_error,
    explain_forecast_error,
)
from sales_data_analyzer.importing import ImportValidationError

FOLDER_NOT_WRITABLE = "Not done: the folder cannot be written. No file was created."


def describe_failure(error: BaseException) -> str:
    """Return the message shown for an exception raised by a window action.

    Never includes raw input values or file contents: application and import
    errors are designed to be safe to show; unknown errors show only their type.
    """
    if isinstance(error, ImportValidationError):
        return describe_import_error(error)
    if isinstance(error, ConcurrentChangeError):
        return f"Not saved: {error}. Nothing was changed."
    if isinstance(error, (PersistenceError, StorageLimitError)):
        return f"Not done: {error}. Nothing was changed."
    if isinstance(error, ChartWriteError):
        return FOLDER_NOT_WRITABLE
    if isinstance(error, (InsufficientHistoryError, NoSalesInSelectionError)):
        return explain_forecast_error(error)
    if isinstance(error, (ApplicationError, ValueError, TypeError)):
        return f"Not done: {error}."
    return f"Unexpected error ({type(error).__name__}). Your data is unchanged."
