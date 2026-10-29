"""Storage interface owned by the application layer.

Use cases talk to persistence only through `SalesRepository`, so they run without a
database in tests (level 2 behavior) and the SQL stays in the `persistence` adapter.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.domain.sales_dataset import SalesDataset


@dataclass(frozen=True)
class StoredCompany:
    """One company as loaded from storage, built only through domain constructors.

    Catalog products and sale items share the same Product instances, so an edit
    of a product is visible in every sale that references it.
    """

    company: Company
    products: tuple[Product, ...]
    sales: SalesDataset


class SalesRepository(ABC):
    """Durable storage for companies, catalogs and sales.

    Every write method is one transaction: either all of its rows are stored or none
    are. Storage failures raise PersistenceError. Methods taking a Company require a
    company returned by `load()` or previously passed to `add_company()`; any other
    company is a programming error (LookupError).
    """

    @property
    @abstractmethod
    def location(self) -> str | None:
        """Return a description of where data lives, shown to the user (None if not a file)."""

    @abstractmethod
    def load(self) -> tuple[StoredCompany, ...]:
        """Return every stored company in creation order, with products and sales."""

    @abstractmethod
    def add_company(self, company: Company) -> None:
        """Store a new company."""

    @abstractmethod
    def add_product(self, company: Company, product: Product) -> None:
        """Store a new catalog product of company."""

    @abstractmethod
    def add_sales(
        self, company: Company, new_products: Sequence[Product], sales: Sequence[Sale]
    ) -> None:
        """Store new catalog products and new sales with their items in one transaction."""

    @abstractmethod
    def close(self) -> None:
        """Release the storage; the repository must not be used afterwards."""
