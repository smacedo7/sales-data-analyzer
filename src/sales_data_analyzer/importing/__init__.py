"""Atomic UTF-8 CSV import; domain objects remain independent of parsing."""
from abc import ABC, abstractmethod
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from sales_data_analyzer.domain.company import Company
from sales_data_analyzer.domain.product import Product
from sales_data_analyzer.domain.sale import Sale
from sales_data_analyzer.domain.sales_dataset import SalesDataset

FIELDS = ("sale_id", "date_time", "product_id", "product", "category",
          "quantity", "unit_price", "unit_cost")


class ImportValidationError(ValueError):
    """Structured safe diagnostic with physical line, field and reason."""

    def __init__(self, line: int, field: str, reason: str) -> None:
        """Keep diagnostics free of input values and filesystem paths."""
        self.line, self.field, self.reason = line, field, reason
        super().__init__(f"line {line}, field {field}: {reason}")


@dataclass(frozen=True)
class ValidatedRow:
    """Parser-independent typed transaction item."""
    sale_id: str
    date_time: datetime
    product_id: str
    product: str
    category: str
    quantity: int
    unit_price: Decimal
    unit_cost: Decimal


class SalesValidator:
    """Validate strings without modifying company or catalog state.

    Accept extended ISO timestamps with seconds, optional fractional seconds,
    and optional Z or HH:MM offset. Aware values normalize to UTC; naive values
    remain local. Each file must use one awareness policy.
    """

    def validate(self, values: dict[str, str], line: int) -> ValidatedRow:
        """Return a typed row or raise a field-specific ImportValidationError."""
        cleaned: dict[str, str] = {}
        for field in FIELDS:
            value = values.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ImportValidationError(line, field, "required non-empty field")
            cleaned[field] = value.strip()
        stamp = cleaned["date_time"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?", stamp):
            raise ImportValidationError(line, "date_time", "expected ISO YYYY-MM-DDTHH:MM:SS with optional fraction/offset")
        try:
            # datetime permits offset minute overflow; reject it explicitly.
            if stamp[-6:-5] in ("+", "-") and (int(stamp[-5:-3]) > 23 or int(stamp[-2:]) > 59):
                raise ValueError
            timestamp = datetime.fromisoformat(stamp)
            if timestamp.utcoffset() is not None:
                timestamp = timestamp.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            raise ImportValidationError(line, "date_time", "invalid calendar date or UTC offset") from None
        if not re.fullmatch(r"[0-9]+", cleaned["quantity"]):
            raise ImportValidationError(line, "quantity", "expected positive integer")
        try:
            quantity = int(cleaned["quantity"])
        except ValueError:
            raise ImportValidationError(line, "quantity", "integer exceeds supported size") from None
        if quantity <= 0:
            raise ImportValidationError(line, "quantity", "expected positive integer")
        amounts: dict[str, Decimal] = {}
        for field in ("unit_price", "unit_cost"):
            text = cleaned[field]
            if not re.fullmatch(r"[+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", text):
                raise ImportValidationError(line, field, "expected finite non-negative decimal without exponent")
            try:
                amount = Decimal(text)
            except InvalidOperation:
                raise ImportValidationError(line, field, "invalid decimal") from None
            if not amount.is_finite() or amount < 0:
                raise ImportValidationError(line, field, "expected finite non-negative decimal")
            amounts[field] = amount
        return ValidatedRow(cleaned["sale_id"], timestamp, cleaned["product_id"],
                            cleaned["product"], cleaned["category"], quantity,
                            amounts["unit_price"], amounts["unit_cost"])


class DataImporter(ABC):
    """Polymorphic import boundary returning a fully validated dataset."""

    @abstractmethod
    def load(self, path: str | Path, company: Company) -> SalesDataset:
        """Load sales for an explicitly supplied existing company."""
        raise NotImplementedError


class CSVImporter(DataImporter):
    """Build local objects and publish only after the entire file succeeds.

    Headers may be reordered but must match FIELDS exactly. Blank records,
    unknown columns and duplicate headers fail. UTF-8 BOM and CSV quoting are
    supported. Sale/product order follows first appearance; every item survives.
    """

    def load(self, path: str | Path, company: Company) -> SalesDataset:
        """Return complete sales or raise ImportValidationError; never mutate company."""
        if not isinstance(company, Company):
            raise TypeError("company must be a Company")
        if not isinstance(path, (str, Path)):
            raise TypeError("path must be a string or Path")
        products: dict[str, Product] = {}
        sales: dict[str, Sale] = {}
        validator = SalesValidator()
        reader = None
        line = 1
        try:
            with open(path, encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream, strict=True)
                header = next(reader, None)
                if header is None:
                    raise ImportValidationError(1, "header", "empty file")
                if len(header) != len(set(header)):
                    raise ImportValidationError(1, "header", "duplicate columns")
                if set(header) != set(FIELDS):
                    raise ImportValidationError(1, "header", "columns must match required schema exactly")
                while True:
                    line = reader.line_num + 1
                    cells = next(reader, None)
                    if cells is None:
                        break
                    if len(cells) != len(header):
                        raise ImportValidationError(line, "record", "incorrect column count")
                    row = validator.validate(dict(zip(header, cells, strict=True)), line)
                    if sales and ((row.date_time.utcoffset() is None) !=
                                  (next(iter(sales.values())).date_time.utcoffset() is None)):
                        raise ImportValidationError(line, "date_time", "cannot mix naive and aware timestamps")
                    sale = sales.get(row.sale_id)
                    if sale is not None and sale.date_time != row.date_time:
                        raise ImportValidationError(line, "date_time", "sale ID has inconsistent timestamp")
                    product = products.get(row.product_id)
                    if product is not None and (product.name, product.category) != (row.product, row.category):
                        raise ImportValidationError(line, "product_id", "product ID has inconsistent name/category")
                    if product is None:
                        product = Product(row.product_id, company, row.product, row.category)
                        products[row.product_id] = product
                    if sale is None:
                        sale = Sale(row.sale_id, company, row.date_time)
                        sales[row.sale_id] = sale
                    sale.add_item(product, row.quantity, row.unit_price, row.unit_cost)
        except UnicodeError:
            raise ImportValidationError(line, "file", "expected UTF-8 encoding") from None
        except OSError:
            raise ImportValidationError(0, "file", "cannot read file") from None
        except csv.Error:
            raise ImportValidationError(line, "record", "malformed CSV quoting or field size") from None
        if not sales:
            raise ImportValidationError(2, "record", "file contains no items")
        dataset = SalesDataset(company)
        for sale in sales.values():
            dataset.add_sale(sale)
        return dataset
