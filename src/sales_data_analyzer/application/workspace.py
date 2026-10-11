"""One company's catalog and sales, changed only through all-or-nothing operations.

Every operation validates first, builds candidate collections, and replaces the
workspace's references only after the domain accepted everything. A refused
operation therefore leaves the workspace exactly as it was.
"""

from collections.abc import Sequence
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
    TimestampAwarenessError,
    UnknownProductError,
)


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


class CompanyWorkspace:
    """Everything recorded for one company during the session.

    Product IDs are unique in the catalog and sale IDs are unique in the sales;
    both are company-scoped strings that keep leading zeros.
    """

    def __init__(self, company: Company) -> None:
        """Create an empty workspace for an existing Company."""
        if not isinstance(company, Company):
            raise TypeError("company must be a Company")
        self._company = company
        self._catalog: dict[str, Product] = {}
        self._sales = SalesDataset(company)

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
        DuplicateProductError when the trimmed ID already exists.
        """
        product = Product(product_id, self._company, name, category)
        if product.id in self._catalog:
            raise DuplicateProductError(product.id)
        self._catalog[product.id] = product
        return product

    def find_product(self, product_id: str) -> Product | None:
        """Return the catalog product with the trimmed ID, or None."""
        if not isinstance(product_id, str):
            raise TypeError("product_id must be a string")
        return self._catalog.get(product_id.strip())

    # -- manual sales -------------------------------------------------------------

    def has_sale(self, sale_id: str) -> bool:
        """Return True when a sale with the trimmed ID already exists."""
        if not isinstance(sale_id, str):
            raise TypeError("sale_id must be a string")
        key = sale_id.strip()
        return any(sale.id == key for sale in self._sales.sales)

    def record_sale(self, sale_id: str, date_time: datetime, items: Sequence[ItemInput]) -> Sale:
        """Store a new sale built from catalog products, all or nothing.

        Checks, in order: duplicate sale ID (DuplicateSaleError), no items
        (EmptySaleError), product missing from the catalog (UnknownProductError)
        and mixing timestamps with and without offsets (TimestampAwarenessError).
        Offsets are normalized to UTC, as imports do. Item values are validated
        by the domain (TypeError/ValueError). Prices and costs are stored
        exactly as given and never derived from the catalog.
        """
        if self.has_sale(sale_id):
            raise DuplicateSaleError((sale_id.strip(),))
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
            date_time = date_time.astimezone(timezone.utc)
        if self._sales.sales and (
            _is_aware(self._sales.sales[0]) != (date_time.utcoffset() is not None)
        ):
            raise TimestampAwarenessError()

        sale = Sale(sale_id, self._company, date_time)
        for product, item in zip(products, items, strict=True):
            sale.add_item(product, item.quantity, item.unit_price, item.unit_cost)
        candidate = self._copy_sales()
        candidate.add_sale(sale)
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
        prices and costs are kept exactly as imported.
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
        items_added = 0
        for sale in imported.sales:
            rebuilt = Sale(sale.id, self._company, sale.date_time)
            for item in sale.items:
                rebuilt.add_item(
                    catalog[item.product.id], item.quantity, item.unit_price, item.unit_cost
                )
                items_added += 1
            candidate.add_sale(rebuilt)

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
