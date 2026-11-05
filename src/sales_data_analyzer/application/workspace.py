"""One company's catalog and sales, changed only through all-or-nothing operations.

Every operation validates first, builds candidate collections, writes them to the
repository (when there is one) in one transaction, and replaces the workspace's
references only after that write succeeded. A refused or failed operation therefore
leaves the workspace, and the stored data, exactly as they were.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.domain.sales_dataset import SalesDataset
from sales_data_analyzer.importing import CSVImporter, DataImporter

from .errors import (
    CatalogConflictError,
    DuplicateProductError,
    DuplicateSaleError,
    EmptySaleError,
    ProductInUseError,
    ProductNotFoundError,
    SaleNotFoundError,
    StorageLimitError,
    TimestampAwarenessError,
    UnknownProductError,
)
from .repository import MAX_STORED_INTEGER, SalesRepository, StoredCompany


@dataclass(frozen=True)
class ItemInput:
    """One item typed for a manual sale; values are validated by SaleItem."""

    product_id: str
    quantity: int
    unit_price: Decimal
    unit_cost: Decimal


@dataclass(frozen=True)
class ImportSummary:
    """Counts reported after a successful import."""

    sales_added: int
    items_added: int
    new_products: int
    reused_products: int


def _is_aware(sale: Sale) -> bool:
    """Return True when the sale timestamp carries a UTC offset."""
    return sale.date_time.utcoffset() is not None


def _require_storable(sales: Iterable[Sale]) -> None:
    """Raise StorageLimitError when an item quantity exceeds the stored integer range."""
    if any(item.quantity > MAX_STORED_INTEGER for sale in sales for item in sale.items):
        raise StorageLimitError()


class CompanyWorkspace:
    """Everything recorded for one company during the session.

    Product IDs are unique in the catalog and sale IDs are unique in the sales;
    both are company-scoped strings that keep leading zeros.
    """

    def __init__(self, company: Company, repository: SalesRepository | None = None) -> None:
        """Create an empty workspace for an existing Company.

        With a repository, every change is stored before it becomes visible; without
        one the workspace lives in memory only (level 2 behavior).
        """
        if not isinstance(company, Company):
            raise TypeError("company must be a Company")
        if repository is not None and not isinstance(repository, SalesRepository):
            raise TypeError("repository must be a SalesRepository")
        self._company = company
        self._repository = repository
        self._catalog: dict[str, Product] = {}
        self._sales = SalesDataset(company)

    @classmethod
    def from_stored(cls, stored: StoredCompany, repository: SalesRepository) -> "CompanyWorkspace":
        """Restore a workspace loaded by a repository, sharing its domain objects."""
        if not isinstance(stored, StoredCompany):
            raise TypeError("stored must be a StoredCompany")
        workspace = cls(stored.company, repository)
        workspace._catalog = {product.id: product for product in stored.products}
        workspace._sales = stored.sales
        return workspace

    @property
    def company(self) -> Company:
        """Return the workspace's company."""
        return self._company

    @property
    def products(self) -> tuple[Product, ...]:
        """Return catalog products ordered by ID."""
        return tuple(self._catalog[key] for key in sorted(self._catalog))

    @property
    def sales(self) -> SalesDataset:
        """Return all sales of the company (shared, not copied)."""
        return self._sales

    # -- catalog ----------------------------------------------------------------

    def register_product(self, product_id: str, name: str, category: str) -> Product:
        """Add a product to the catalog and return it.

        Raise TypeError/ValueError for invalid values (domain validation) and
        DuplicateProductError when the trimmed ID already exists. With a repository,
        storage failures raise PersistenceError and the catalog is unchanged.
        """
        product = Product(product_id, self._company, name, category)
        if product.id in self._catalog:
            raise DuplicateProductError(product.id)
        if self._repository is not None:
            self._repository.add_product(self._company, product)
        self._catalog[product.id] = product
        return product

    def find_product(self, product_id: str) -> Product | None:
        """Return the catalog product with the trimmed ID, or None."""
        if not isinstance(product_id, str):
            raise TypeError("product_id must be a string")
        return self._catalog.get(product_id.strip())

    def update_product(self, product_id: str, name: str | None, category: str | None) -> Product:
        """Change the name and/or category of a catalog product; None keeps a value.

        Both values are validated before anything is written (TypeError/ValueError),
        so a refused category never leaves a changed name behind. Raise
        ProductNotFoundError for an unknown ID. Sale items share the product, so
        analyses show the new name; stored prices and costs never change.
        """
        product = self._require_product(product_id)
        edited = Product(
            product.id,
            self._company,
            product.name if name is None else name,
            product.category if category is None else category,
        )
        if self._repository is not None:
            self._repository.update_product(self._company, product.id, edited.name, edited.category)
        product.name = edited.name
        product.category = edited.category
        return product

    def sales_with_product(self, product_id: str) -> int:
        """Return how many sales contain the catalog product (ProductNotFoundError if unknown)."""
        product = self._require_product(product_id)
        return sum(1 for sale in self._sales.sales if any(i.product is product for i in sale.items))

    def delete_product(self, product_id: str) -> None:
        """Remove a product that no sale uses.

        Raise ProductNotFoundError for an unknown ID and ProductInUseError (with the
        sale count) when sales reference it; sold products are never deleted.
        """
        product = self._require_product(product_id)
        in_use = self.sales_with_product(product.id)
        if in_use:
            raise ProductInUseError(in_use)
        if self._repository is not None:
            self._repository.delete_product(self._company, product.id)
        catalog = dict(self._catalog)
        del catalog[product.id]
        self._catalog = catalog

    def _require_product(self, product_id: str) -> Product:
        """Return the catalog product with the trimmed ID or raise ProductNotFoundError."""
        product = self.find_product(product_id)
        if product is None:
            raise ProductNotFoundError(product_id.strip())
        return product

    # -- manual sales -------------------------------------------------------------

    def has_sale(self, sale_id: str) -> bool:
        """Return True when a sale with the trimmed ID already exists."""
        return self.find_sale(sale_id) is not None

    def find_sale(self, sale_id: str) -> Sale | None:
        """Return the sale with the trimmed ID, or None."""
        if not isinstance(sale_id, str):
            raise TypeError("sale_id must be a string")
        key = sale_id.strip()
        return next((sale for sale in self._sales.sales if sale.id == key), None)

    def list_sales(self, sales: SalesDataset | None = None) -> tuple[Sale, ...]:
        """Return sales in insertion order: all of them, or those of a selected dataset."""
        if sales is None:
            return self._sales.sales
        if not isinstance(sales, SalesDataset) or sales.company is not self._company:
            raise TypeError("sales must be a SalesDataset of this company")
        return sales.sales

    def delete_sale(self, sale_id: str) -> Sale:
        """Remove a sale and its items, all or nothing, and return it.

        Raise SaleNotFoundError for an unknown ID. With a repository, a storage
        failure (PersistenceError) leaves the sales unchanged.
        """
        sale = self.find_sale(sale_id)
        if sale is None:
            raise SaleNotFoundError(sale_id.strip())
        candidate = SalesDataset(self._company)
        for kept in self._sales.sales:
            if kept is not sale:
                candidate.add_sale(kept)
        if self._repository is not None:
            self._repository.delete_sale(self._company, sale.id)
        self._sales = candidate
        return sale

    def record_sale(self, sale_id: str, date_time: datetime, items: Sequence[ItemInput]) -> Sale:
        """Store a new sale built from catalog products, all or nothing.

        Checks, in order: duplicate sale ID (DuplicateSaleError), no items
        (EmptySaleError), product missing from the catalog (UnknownProductError)
        and mixing timestamps with and without offsets (TimestampAwarenessError).
        Offsets are normalized to UTC, as imports do. Item values are validated
        by the domain (TypeError/ValueError); items that are not an iterable of
        ItemInput raise TypeError. Prices and costs are stored
        exactly as given and never derived from the catalog. With a repository,
        StorageLimitError and PersistenceError leave everything unchanged.
        """
        if self.has_sale(sale_id):
            raise DuplicateSaleError((sale_id.strip(),))
        if isinstance(items, (str, bytes)) or not isinstance(items, Iterable):
            raise TypeError("items must be a sequence of ItemInput values")
        items = tuple(items)
        if not items:
            raise EmptySaleError()
        if not isinstance(date_time, datetime):
            raise TypeError("date_time must be a datetime")
        products = []
        for item in items:
            if not isinstance(item, ItemInput):
                raise TypeError("items must be ItemInput values")
            product = self.find_product(item.product_id)
            if product is None:
                raise UnknownProductError(item.product_id.strip())
            products.append(product)
        if date_time.utcoffset() is not None:
            try:
                date_time = date_time.astimezone(timezone.utc)
            except OverflowError:
                raise ValueError("the sale date and time is outside the supported range") from None
        if self._sales.sales and (
            _is_aware(self._sales.sales[0]) != (date_time.utcoffset() is not None)
        ):
            raise TimestampAwarenessError()

        sale = Sale(sale_id, self._company, date_time)
        for product, item in zip(products, items, strict=True):
            sale.add_item(product, item.quantity, item.unit_price, item.unit_cost)
        candidate = self._copy_sales()
        candidate.add_sale(sale)
        if self._repository is not None:
            _require_storable((sale,))
            self._repository.add_sales(self._company, (), (sale,))
        self._sales = candidate
        return sale

    # -- import -----------------------------------------------------------------

    def import_sales(self, path: str | Path, importer: DataImporter | None = None) -> ImportSummary:
        """Import a sales file into this company, all or nothing.

        The file is validated by the importer (ImportValidationError on bad
        content). Then, in order: any sale ID already in the company raises
        DuplicateSaleError; any product ID whose trimmed name or category differs
        from the catalog raises CatalogConflictError; mixing timestamps with and
        without offsets raises TimestampAwarenessError. Identical catalog
        products are reused; new products join the catalog. Item quantities,
        prices and costs are kept exactly as imported. With a repository, the
        products, sales and items are stored in one transaction before they
        become visible (StorageLimitError/PersistenceError change nothing).
        """
        if importer is None:
            importer = CSVImporter()
        if not isinstance(importer, DataImporter):
            raise TypeError("importer must be a DataImporter")
        imported = importer.load(path, self._company)

        existing_ids = {sale.id for sale in self._sales.sales}
        duplicates = tuple(sale.id for sale in imported.sales if sale.id in existing_ids)
        if duplicates:
            raise DuplicateSaleError(duplicates)

        file_products: dict[str, Product] = {}
        for sale in imported.sales:
            for item in sale.items:
                file_products.setdefault(item.product.id, item.product)
        conflicts = tuple(
            product_id
            for product_id, product in file_products.items()
            if product_id in self._catalog
            and (self._catalog[product_id].name, self._catalog[product_id].category)
            != (product.name, product.category)
        )
        if conflicts:
            raise CatalogConflictError(conflicts)

        if self._sales.sales and imported.sales:
            if _is_aware(self._sales.sales[0]) != _is_aware(imported.sales[0]):
                raise TimestampAwarenessError()

        catalog = dict(self._catalog)
        reused = sum(1 for product_id in file_products if product_id in catalog)
        for product_id, product in file_products.items():
            catalog.setdefault(product_id, product)

        candidate = self._copy_sales()
        rebuilt_sales: list[Sale] = []
        items_added = 0
        for sale in imported.sales:
            rebuilt = Sale(sale.id, self._company, sale.date_time)
            for item in sale.items:
                rebuilt.add_item(
                    catalog[item.product.id], item.quantity, item.unit_price, item.unit_cost
                )
                items_added += 1
            candidate.add_sale(rebuilt)
            rebuilt_sales.append(rebuilt)

        if self._repository is not None:
            _require_storable(rebuilt_sales)
            new_products = [p for key, p in catalog.items() if key not in self._catalog]
            self._repository.add_sales(self._company, new_products, rebuilt_sales)
        self._catalog = catalog
        self._sales = candidate
        return ImportSummary(
            sales_added=len(imported.sales),
            items_added=items_added,
            new_products=len(file_products) - reused,
            reused_products=reused,
        )

    def _copy_sales(self) -> SalesDataset:
        """Return a new dataset associating the current sales, for candidate changes."""
        candidate = SalesDataset(self._company)
        for sale in self._sales.sales:
            candidate.add_sale(sale)
        return candidate
