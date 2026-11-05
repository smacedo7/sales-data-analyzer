"""Qt-free, translated wording of failures shown by the desktop window (one error funnel).

Each application error type has its own sentence, filled from the error's typed
attributes (counts, IDs, line and column) instead of its English message.
Specific subclasses are tested before their ValueError bases.
"""

from sales_data_analyzer.application import (
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
    ProductInUseError,
    ProductNotFoundError,
    SaleNotFoundError,
    StorageLimitError,
    TimestampAwarenessError,
    UnknownProductError,
)
from sales_data_analyzer.charts.images import ChartWriteError
from sales_data_analyzer.importing import ImportValidationError

from .pdf_report import ReportWriteError
from .texts import id_list, t


def describe_import_refusal(error: DuplicateSaleError | CatalogConflictError) -> str:
    """Explain an import refused by the company's data, naming up to five IDs."""
    if isinstance(error, DuplicateSaleError):
        return t("error.import_duplicate", count=len(error.sale_ids), ids=id_list(error.sale_ids))
    return t("error.import_conflict", count=len(error.product_ids), ids=id_list(error.product_ids))


def describe_failure(error: BaseException) -> str:
    """Return the message shown for an exception raised by a window action.

    Never includes file paths or raw file contents; unknown errors show only
    their type, so a bug never leaks data into a dialog.
    """
    if isinstance(error, ImportValidationError):
        if error.line == 0:
            return t("error.import_file", reason=error.reason)
        return t("error.import_line", line=error.line, field=error.field, reason=error.reason)
    simple = {
        NoCompanySelectedError: "error.needs_company",
        DuplicateCompanyError: "error.duplicate_company",
        CompanyNotFoundError: "error.company_not_found",
        EmptySaleError: "error.empty_sale",
        TimestampAwarenessError: "error.timezone_mix",
        NoSalesInSelectionError: "error.no_sales",
        ConcurrentChangeError: "error.concurrent",
        StorageLimitError: "error.storage_limit",
        ChartWriteError: "error.folder",
        ReportWriteError: "report.write_failed",
    }
    for kind, key in simple.items():
        if isinstance(error, kind):
            return t(key)
    if isinstance(error, PersistenceError):
        return t("error.storage")
    if isinstance(error, (DuplicateProductError, UnknownProductError, ProductNotFoundError)):
        key = {
            DuplicateProductError: "error.duplicate_product",
            UnknownProductError: "error.unknown_product",
            ProductNotFoundError: "error.product_not_found",
        }[type(error)]
        return t(key, id=error.product_id)
    if isinstance(error, DuplicateSaleError):
        return t("error.duplicate_sale", count=len(error.sale_ids), ids=id_list(error.sale_ids))
    if isinstance(error, ProductInUseError):
        return t("error.in_use", count=error.sale_count)
    if isinstance(error, SaleNotFoundError):
        return t("error.sale_not_found", id=error.sale_id)
    if isinstance(error, InvalidPeriodError):
        reversed_ = "before the start" in str(error)
        return t("error.period_reversed" if reversed_ else "error.period_range")
    if isinstance(error, InsufficientHistoryError):
        from .reports import explain_forecast_refusal

        return explain_forecast_refusal(error)
    if isinstance(error, (ApplicationError, ValueError, TypeError)):
        return t("error.invalid_value", detail=str(error))
    return t("error.unexpected", kind=type(error).__name__)
