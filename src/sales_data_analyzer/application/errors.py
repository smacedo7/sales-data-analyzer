"""Errors raised by application use cases.

Messages carry counts only, never IDs, raw values or file paths, so they are
safe to log or display as-is. Adapters read the typed attributes when they
need to show details to the user.
"""


class ApplicationError(ValueError):
    """Base class for rule violations detected by the application layer."""


class NoCompanySelectedError(ApplicationError):
    """Raised when an operation needs a selected company and none is set."""

    def __init__(self) -> None:
        super().__init__("no company is selected")


class DuplicateCompanyError(ApplicationError):
    """Raised when a company name is already used in the session."""

    def __init__(self) -> None:
        super().__init__("a company with this name already exists")


class CompanyNotFoundError(ApplicationError):
    """Raised when a company list position does not exist."""

    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"choose a company number from 1 to {count}")


class DuplicateProductError(ApplicationError):
    """Raised when a product ID already exists in the company catalog."""

    def __init__(self, product_id: str) -> None:
        self.product_id = product_id
        super().__init__("this product ID already exists in the catalog")


class UnknownProductError(ApplicationError):
    """Raised when a sale item references a product missing from the catalog."""

    def __init__(self, product_id: str) -> None:
        self.product_id = product_id
        super().__init__("the product ID is not in the catalog")


class EmptySaleError(ApplicationError):
    """Raised when a sale would be stored without items."""

    def __init__(self) -> None:
        super().__init__("a sale needs at least one item")


class DuplicateSaleError(ApplicationError):
    """Raised when sale IDs already exist in the company."""

    def __init__(self, sale_ids: tuple[str, ...]) -> None:
        self.sale_ids = sale_ids
        super().__init__(f"{len(sale_ids)} sale ID(s) already exist in this company")


class CatalogConflictError(ApplicationError):
    """Raised when imported products disagree with the catalog for the same ID."""

    def __init__(self, product_ids: tuple[str, ...]) -> None:
        self.product_ids = product_ids
        super().__init__(
            f"{len(product_ids)} product ID(s) have a different name or category in the catalog"
        )


class TimestampAwarenessError(ApplicationError):
    """Raised when sales with and without UTC offsets would be mixed."""

    def __init__(self) -> None:
        super().__init__("sales with and without time zone offsets cannot be mixed in one company")


class InvalidPeriodError(ApplicationError):
    """Raised when a period is reversed or outside the supported calendar."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)


class NoSalesInSelectionError(ApplicationError):
    """Raised when an operation needs sales and the selection has none."""

    def __init__(self) -> None:
        super().__init__("there are no sales in the current selection")


class InsufficientHistoryError(ApplicationError):
    """Raised when the forecast lacks enough calendar days of history."""

    def __init__(self, available_days: int, required_days: int) -> None:
        self.available_days = available_days
        self.required_days = required_days
        super().__init__(
            f"{available_days} day(s) of history available, at least {required_days} needed"
        )
